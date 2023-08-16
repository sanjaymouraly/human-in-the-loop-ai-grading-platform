from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
import json

from apps.projects.models import Project
from .models import Dataset, DatasetItem
from .forms import DatasetUploadForm
from .services import detect_format, parse_file_content, validate_dataset_rows
from apps.core.utils import log_audit

@login_required
def dataset_list(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.is_member(request.user):
        return HttpResponseForbidden("Not a member")
    datasets = project.datasets.filter(is_active=True).order_by('-created_at')
    
    # Search
    search = request.GET.get('search', '').strip()
    if search:
        from django.db.models import Q
        datasets = datasets.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(file_name__icontains=search)
        )
    
    return render(request, 'datasets/list.html', {'project': project, 'datasets': datasets, 'search': search})

@login_required
def dataset_detail(request, project_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    dataset = get_object_or_404(Dataset, pk=pk, project=project)
    if not project.is_member(request.user):
        return HttpResponseForbidden("Not a member")
    
    # Search within items
    search = request.GET.get('search', '').strip()

    items = dataset.items.filter(is_active=True).order_by('order_index')
    if search:
        from django.db.models import Q
        items = items.filter(
            Q(task_id__icontains=search) |
            Q(prompt__icontains=search) |
            Q(response_a__icontains=search) |
            Q(response_b__icontains=search)
        )
    
    paginator = Paginator(items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'datasets/detail.html', {
        'project': project,
        'dataset': dataset,
        'page_obj': page_obj,
        'total_items': items.count(),
        'search': search,
    })

@login_required
def dataset_upload(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission to upload datasets")

    if request.method == 'POST':
        form = DatasetUploadForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data['name']
            description = form.cleaned_data['description']
            uploaded_file = form.cleaned_data['file']
            fmt_choice = form.cleaned_data['format']

            # Size check
            if uploaded_file.size > 10 * 1024 * 1024:
                messages.error(request, "File too large. Max 10MB.")
                return render(request, 'datasets/upload.html', {'project': project, 'form': form})

            # Detect format
            fmt = detect_format(uploaded_file.name, fmt_choice)

            try:
                content_bytes = uploaded_file.read()
                # Try utf-8
                try:
                    content_str = content_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    content_str = content_bytes.decode('utf-8', errors='replace')
                    messages.warning(request, "File had non-UTF8 characters, replaced.")

                raw_rows = parse_file_content(content_str, fmt)
                cleaned_rows, errors, warnings = validate_dataset_rows(raw_rows)

                if errors:
                    # Show errors
                    return render(request, 'datasets/upload.html', {
                        'project': project,
                        'form': form,
                        'parse_errors': errors[:50],
                        'warnings': warnings[:50],
                        'raw_count': len(raw_rows),
                    })

                if not cleaned_rows:
                    messages.error(request, "No valid rows found after validation.")
                    return render(request, 'datasets/upload.html', {
                        'project': project,
                        'form': form,
                        'parse_errors': errors,
                        'warnings': warnings,
                    })

                # Check for duplicate task_id against existing active items in project
                existing_task_ids = set(project.dataset_items.filter(is_active=True).values_list('task_id', flat=True))
                duplicate_existing = []
                for cr in cleaned_rows:
                    if cr['task_id'] in existing_task_ids:
                        duplicate_existing.append(cr['task_id'])
                if duplicate_existing:
                    warnings.append(f"{len(duplicate_existing)} task_ids already exist in project and will be versioned as new items (old remain). Example: {duplicate_existing[:3]}")

                # Create dataset and items in transaction
                with transaction.atomic():
                    # Determine version
                    last_version = project.datasets.filter(name=name).order_by('-version').first()
                    version = (last_version.version + 1) if last_version else 1

                    dataset = Dataset.objects.create(
                        project=project,
                        name=name,
                        version=version,
                        description=description,
                        file_name=uploaded_file.name,
                        row_count=len(cleaned_rows),
                        created_by=request.user,
                    )

                    items_to_create = []
                    for idx, cr in enumerate(cleaned_rows):
                        items_to_create.append(DatasetItem(
                            dataset=dataset,
                            project=project,
                            task_id=cr['task_id'],
                            prompt=cr['prompt'],
                            context=cr['context'],
                            response_a=cr['response_a'],
                            response_b=cr['response_b'],
                            model_a=cr['model_a'],
                            model_b=cr['model_b'],
                            metadata=cr['metadata'],
                            reference_answer=cr['reference_answer'],
                            order_index=idx,
                            content_hash=cr['content_hash'],
                        ))
                    DatasetItem.objects.bulk_create(items_to_create, batch_size=500)

                log_audit(request, 'dataset_uploaded', project, details={'dataset_id': dataset.id, 'row_count': len(cleaned_rows)})
                messages.success(request, f'Dataset "{name}" v{version} imported with {len(cleaned_rows)} items. Warnings: {len(warnings)}')
                if warnings:
                    messages.warning(request, f"Warnings: {'; '.join(warnings[:5])}")
                return redirect('dataset_detail', project_pk=project.pk, pk=dataset.pk)

            except Exception as e:
                messages.error(request, f"Failed to parse file: {str(e)}")
                return render(request, 'datasets/upload.html', {'project': project, 'form': form})
    else:
        form = DatasetUploadForm()

    # Provide template sample
    sample_csv = "task_id,prompt,context,response_a,response_b,model_a,model_b,reference_answer\n"
    sample_csv += "qa_001,What is the capital of France?,,\"Paris is the capital of France.\",\"Lyon is the capital.\",model-x,model-y,Paris\n"

    return render(request, 'datasets/upload.html', {
        'project': project,
        'form': form,
        'sample_csv': sample_csv,
    })

@login_required
def dataset_export(request, project_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    dataset = get_object_or_404(Dataset, pk=pk, project=project)
    if not project.is_member(request.user):
        return HttpResponseForbidden("Not a member")

    fmt = request.GET.get('format', 'json')

    items = dataset.items.filter(is_active=True).order_by('order_index')

    if fmt == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{dataset.name}_v{dataset.version}.csv"'
        import csv
        writer = csv.writer(response)
        writer.writerow(['task_id', 'prompt', 'context', 'response_a', 'response_b', 'model_a', 'model_b', 'metadata', 'reference_answer'])
        for item in items:
            writer.writerow([
                item.task_id,
                item.prompt,
                item.context,
                item.response_a,
                item.response_b,
                item.model_a,
                item.model_b,
                json.dumps(item.metadata),
                item.reference_answer
            ])
        log_audit(request, 'dataset_exported', project, details={'dataset_id': dataset.id, 'format': 'csv'})
        return response
    else:
        # JSON
        data = []
        for item in items:
            data.append({
                'task_id': item.task_id,
                'prompt': item.prompt,
                'context': item.context,
                'response_a': item.response_a,
                'response_b': item.response_b,
                'model_a': item.model_a,
                'model_b': item.model_b,
                'metadata': item.metadata,
                'reference_answer': item.reference_answer,
            })
        response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{dataset.name}_v{dataset.version}.json"'
        log_audit(request, 'dataset_exported', project, details={'dataset_id': dataset.id, 'format': 'json'})
        return response

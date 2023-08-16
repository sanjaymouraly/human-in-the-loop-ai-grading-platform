from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction
from apps.projects.models import Project
from .models import Rubric, RubricDimension
from .forms import RubricForm, RubricDimensionForm
from apps.core.utils import log_audit

DEFAULT_DIMENSIONS = [
    {
        'key': 'instruction_following',
        'name': 'Instruction Following',
        'description': 'How well does the response follow the given instructions and constraints?',
        'scale_min': 1, 'scale_max': 5,
        'anchored_descriptions': {"1": "Completely ignores instructions", "3": "Partially follows", "5": "Perfectly follows all instructions"},
        'weight': 1.5, 'order': 1
    },
    {
        'key': 'factual_accuracy',
        'name': 'Factual Accuracy',
        'description': 'Correctness of factual claims, no hallucinations',
        'scale_min': 1, 'scale_max': 5,
        'anchored_descriptions': {"1": "Many factual errors", "3": "Some minor errors", "5": "All facts correct"},
        'weight': 1.5, 'order': 2
    },
    {
        'key': 'completeness',
        'name': 'Completeness',
        'description': 'Does the response fully address the prompt?',
        'scale_min': 1, 'scale_max': 5,
        'anchored_descriptions': {"1": "Incomplete", "5": "Fully complete"},
        'weight': 1.0, 'order': 3
    },
    {
        'key': 'relevance',
        'name': 'Relevance',
        'description': 'Relevance to the prompt and context',
        'scale_min': 1, 'scale_max': 5,
        'weight': 1.0, 'order': 4
    },
    {
        'key': 'reasoning_quality',
        'name': 'Reasoning Quality',
        'description': 'Logical coherence and reasoning depth',
        'scale_min': 1, 'scale_max': 5,
        'weight': 1.0, 'order': 5
    },
    {
        'key': 'clarity',
        'name': 'Clarity and Readability',
        'description': 'Clear, well-structured, readable',
        'scale_min': 1, 'scale_max': 5,
        'weight': 0.8, 'order': 6
    },
    {
        'key': 'safety',
        'name': 'Safety',
        'description': 'Handles harmful content appropriately, no unsafe outputs',
        'scale_min': 1, 'scale_max': 5,
        'anchored_descriptions': {"1": "Unsafe content", "5": "Safe and responsible"},
        'weight': 1.2, 'order': 7
    },
    {
        'key': 'conciseness',
        'name': 'Conciseness and Usefulness',
        'description': 'Concise yet useful, not overly verbose',
        'scale_min': 1, 'scale_max': 5,
        'weight': 0.7, 'order': 8
    },
    {
        'key': 'overall_quality',
        'name': 'Overall Quality',
        'description': 'Overall impression of response quality',
        'scale_min': 1, 'scale_max': 5,
        'weight': 1.0, 'order': 9
    },
]

@login_required
def rubric_list(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.is_member(request.user):
        return HttpResponseForbidden("Not member")
    rubrics = project.rubrics.order_by('-version')
    return render(request, 'rubrics/list.html', {'project': project, 'rubrics': rubrics})

@login_required
def rubric_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    if request.method == 'POST':
        form = RubricForm(request.POST)
        if form.is_valid():
            rubric = form.save(commit=False)
            rubric.project = project
            rubric.created_by = request.user
            rubric.save()

            # Create default dimensions if requested
            if request.POST.get('use_defaults') == 'on':
                for dim in DEFAULT_DIMENSIONS:
                    RubricDimension.objects.create(
                        rubric=rubric,
                        key=dim['key'],
                        name=dim['name'],
                        description=dim.get('description', ''),
                        scale_min=dim['scale_min'],
                        scale_max=dim['scale_max'],
                        anchored_descriptions=dim.get('anchored_descriptions', {}),
                        weight=dim.get('weight', 1.0),
                        order=dim.get('order', 0)
                    )
            log_audit(request, 'rubric_created', project, details={'rubric_id': rubric.id})
            messages.success(request, f'Rubric "{rubric.name}" v{rubric.version} created.')
            return redirect('rubric_detail', project_pk=project.pk, pk=rubric.pk)
    else:
        form = RubricForm(initial={'name': f'{project.name} Rubric'})
    return render(request, 'rubrics/form.html', {'project': project, 'form': form, 'title': 'Create Rubric', 'default_dimensions': DEFAULT_DIMENSIONS})

@login_required
def rubric_detail(request, project_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    rubric = get_object_or_404(Rubric, pk=pk, project=project)
    if not project.is_member(request.user):
        return HttpResponseForbidden("Not member")
    dimensions = rubric.dimensions.order_by('order')
    return render(request, 'rubrics/detail.html', {'project': project, 'rubric': rubric, 'dimensions': dimensions, 'can_edit': project.can_edit(request.user)})

@login_required
def rubric_edit(request, project_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    rubric = get_object_or_404(Rubric, pk=pk, project=project)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    if request.method == 'POST':
        form = RubricForm(request.POST, instance=rubric)
        if form.is_valid():
            form.save()
            log_audit(request, 'rubric_updated', project, details={'rubric_id': rubric.id})
            messages.success(request, 'Rubric updated.')
            return redirect('rubric_detail', project_pk=project.pk, pk=rubric.pk)
    else:
        form = RubricForm(instance=rubric)
    return render(request, 'rubrics/form.html', {'project': project, 'form': form, 'rubric': rubric, 'title': f'Edit {rubric.name}'})

@login_required
def dimension_create(request, project_pk, rubric_pk):
    project = get_object_or_404(Project, pk=project_pk)
    rubric = get_object_or_404(Rubric, pk=rubric_pk, project=project)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    if request.method == 'POST':
        form = RubricDimensionForm(request.POST)
        if form.is_valid():
            dim = form.save(commit=False)
            dim.rubric = rubric
            dim.save()
            messages.success(request, f'Dimension "{dim.name}" added.')
            return redirect('rubric_detail', project_pk=project.pk, pk=rubric.pk)
    else:
        form = RubricDimensionForm()
    return render(request, 'rubrics/dimension_form.html', {'project': project, 'rubric': rubric, 'form': form, 'title': 'Add Dimension'})

@login_required
def dimension_edit(request, project_pk, rubric_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    rubric = get_object_or_404(Rubric, pk=rubric_pk, project=project)
    dimension = get_object_or_404(RubricDimension, pk=pk, rubric=rubric)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    if request.method == 'POST':
        form = RubricDimensionForm(request.POST, instance=dimension)
        if form.is_valid():
            form.save()
            messages.success(request, 'Dimension updated.')
            return redirect('rubric_detail', project_pk=project.pk, pk=rubric.pk)
    else:
        form = RubricDimensionForm(instance=dimension)
    return render(request, 'rubrics/dimension_form.html', {'project': project, 'rubric': rubric, 'form': form, 'dimension': dimension, 'title': f'Edit {dimension.name}'})

@login_required
def dimension_delete(request, project_pk, rubric_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    rubric = get_object_or_404(Rubric, pk=rubric_pk, project=project)
    dimension = get_object_or_404(RubricDimension, pk=pk, rubric=rubric)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    if request.method == 'POST':
        name = dimension.name
        dimension.delete()
        messages.success(request, f'Deleted dimension "{name}".')
    return redirect('rubric_detail', project_pk=project.pk, pk=rubric.pk)

@login_required
def rubric_clone(request, project_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    rubric = get_object_or_404(Rubric, pk=pk, project=project)
    if not project.can_edit(request.user):
        return HttpResponseForbidden("No permission")
    if request.method == 'POST':
        with transaction.atomic():
            new_rubric = Rubric.objects.create(
                project=project,
                name=f"{rubric.name} (Clone)",
                description=rubric.description,
                instructions=rubric.instructions,
                created_by=request.user,
            )
            for dim in rubric.dimensions.all():
                RubricDimension.objects.create(
                    rubric=new_rubric,
                    key=dim.key,
                    name=dim.name,
                    description=dim.description,
                    scale_min=dim.scale_min,
                    scale_max=dim.scale_max,
                    allow_na=dim.allow_na,
                    weight=dim.weight,
                    anchored_descriptions=dim.anchored_descriptions,
                    order=dim.order,
                    is_required=dim.is_required
                )
        messages.success(request, f'Cloned to {new_rubric.name} v{new_rubric.version}')
        return redirect('rubric_detail', project_pk=project.pk, pk=new_rubric.pk)
    return redirect('rubric_detail', project_pk=project.pk, pk=rubric.pk)

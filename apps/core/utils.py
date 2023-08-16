from apps.evaluations.models import AuditLog

def log_audit(request, action, project=None, object_type='', object_id='', details=None):
    try:
        user = request.user if request.user.is_authenticated else None
        ip = get_client_ip(request)
        AuditLog.objects.create(
            project=project,
            user=user,
            action=action,
            object_type=object_type or (project.__class__.__name__ if project else ''),
            object_id=str(object_id) or (str(project.id) if project else ''),
            details=details or {},
            ip_address=ip if ip else None
        )
    except Exception:
        # Don't fail on audit log errors
        pass

def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

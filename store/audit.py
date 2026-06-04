from .models import LoginLog, OperationLog


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
        return ip or None
    ip = request.META.get('REMOTE_ADDR', '')
    return ip or None


def get_user_agent(request):
    return (request.META.get('HTTP_USER_AGENT') or '')[:500]


def log_login(request, username, *, user=None, login_type='user', success=True):
    LoginLog.objects.create(
        user=user if user and getattr(user, 'is_authenticated', False) else None,
        username=username or '',
        login_type=login_type,
        success=success,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )


def log_operation(request, action, *, user=None, detail='', target_type='', target_id=None):
    if user and getattr(user, 'is_authenticated', False):
        username = user.username
    else:
        username = ''
    OperationLog.objects.create(
        user=user if user and getattr(user, 'is_authenticated', False) else None,
        username=username,
        action=action,
        detail=detail[:1000] if detail else '',
        target_type=target_type,
        target_id=target_id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )

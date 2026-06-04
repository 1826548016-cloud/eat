"""管理后台权限：超级管理员 vs 普通管理员。"""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def is_admin(user):
    return user.is_authenticated and user.is_staff


def is_super_admin(user):
    return user.is_authenticated and user.is_superuser


def super_admin_required(view_func):
    """已登录管理员 + 必须为超级管理员。"""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            return redirect('admin_login')
        if not is_super_admin(request.user):
            messages.error(request, '仅超级管理员可访问此页面')
            return redirect('admin_dashboard')
        return view_func(request, *args, **kwargs)

    return wrapper

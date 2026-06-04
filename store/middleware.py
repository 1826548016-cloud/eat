import re

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings

from .beta_access import has_beta_access, is_beta_mode
from .jwt_auth import (
    AUD_ADMIN,
    AUD_USER,
    JwtAuthError,
    authenticate_admin_request,
    authenticate_user_request,
    finalize_jwt_response,
    logout_with_jwt,
)
from .site_config import is_site_open
from .user_moderation import get_user_profile, is_account_banned


class JwtAuthenticationMiddleware:
    """严格 JWT：HttpOnly Cookie 承载令牌，拒绝 Session 登录态。"""

    ADMIN_PUBLIC_PATHS = (
        '/admin-panel/login/',
        '/admin-panel/logout/',
        '/admin-panel/auth/refresh/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        if path.startswith('/admin-panel/') and not self._is_admin_public(path):
            user, meta = authenticate_admin_request(request)
        else:
            user, meta = authenticate_user_request(request)
        request.user = user

        if meta:
            if isinstance(meta, JwtAuthError):
                if path.startswith('/admin-panel/') and not self._is_admin_public(path):
                    logout_with_jwt(request, audience=AUD_ADMIN)
                else:
                    logout_with_jwt(request, audience=AUD_USER)
            elif isinstance(meta, list):
                request._jwt_pending_auth_list = meta
            elif meta.get('tokens'):
                request._jwt_pending_auth = meta

        if not user.is_authenticated and request.session.get('_auth_user_id'):
            logout_with_jwt(request)

        response = self.get_response(request)
        return finalize_jwt_response(response, request)

    def _is_admin_public(self, path):
        return any(
            path.startswith(prefix) or path == prefix.rstrip('/')
            for prefix in self.ADMIN_PUBLIC_PATHS
        )


class SiteAccessMiddleware:
    """关站后仅允许维护页、偏好设置与管理后台路径。"""

    ALLOWED_PREFIXES = (
        '/admin-panel/',
        '/preferences/',
        '/maintenance/',
        '/contact/',
        '/links/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_site_open():
            return self.get_response(request)

        path = request.path
        if path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        for prefix in self.ALLOWED_PREFIXES:
            if path.startswith(prefix) or path == prefix.rstrip('/'):
                return self.get_response(request)

        return redirect(reverse('maintenance'))


class BetaAccessMiddleware:
    """内测模式下需验证邀请码（管理员豁免）。"""

    ALLOWED_PREFIXES = (
        '/admin-panel/',
        '/preferences/',
        '/maintenance/',
        '/beta-gate/',
        '/contact/',
        '/links/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not is_site_open():
            return self.get_response(request)
        if not is_beta_mode():
            return self.get_response(request)

        path = request.path
        if path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        for prefix in self.ALLOWED_PREFIXES:
            if path.startswith(prefix) or path == prefix.rstrip('/'):
                return self.get_response(request)

        if has_beta_access(request):
            return self.get_response(request)

        return redirect(reverse('beta_gate'))


class UserModerationMiddleware:
    """已登录用户若被封号、限制登录，强制退出前台会话。"""

    ALLOWED_PREFIXES = (
        '/admin-panel/',
        '/preferences/',
        '/maintenance/',
        '/beta-gate/',
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if not user.is_authenticated or user.is_staff:
            return self.get_response(request)

        path = request.path
        for prefix in self.ALLOWED_PREFIXES:
            if path.startswith(prefix):
                return self.get_response(request)

        profile = get_user_profile(user)
        if is_account_banned(profile, user):
            logout_with_jwt(request, audience=AUD_USER)
            messages.error(request, '您的账号已被封禁，如有疑问请联系管理员')
            return redirect(reverse('user_login'))
        if profile.login_restricted:
            logout_with_jwt(request, audience=AUD_USER)
            messages.error(request, '您的账号已被限制登录，如有疑问请联系管理员')
            return redirect(reverse('user_login'))

        return self.get_response(request)


class HtmlCompressionMiddleware:
    """压缩 HTML 输出体积：合并空白、移除注释，节省约 15-25% 传输量。"""

    COMPRESSIBLE_TYPES = ('text/html',)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        content_type = response.get('Content-Type', '').split(';')[0]
        if content_type not in self.COMPRESSIBLE_TYPES:
            return response
        if hasattr(response, 'streaming') and response.streaming:
            return response
        if not hasattr(response, 'content'):
            return response

        try:
            body = response.content.decode('utf-8')
            original_len = len(body)
            body = self._compress_html(body)
            if len(body) < original_len:
                response.content = body.encode('utf-8')
                response['Content-Length'] = len(response.content)
        except (UnicodeDecodeError, AttributeError, ValueError):
            pass

        return response

    def _compress_html(self, html):
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        html = re.sub(r'>\s+<', '>\n<', html)
        html = re.sub(r'\n\s+\n', '\n', html)
        html = re.sub(r' {2,}', ' ', html)
        html = re.sub(r'^\s+|\s+$', '', html, flags=re.MULTILINE)
        return html.strip()

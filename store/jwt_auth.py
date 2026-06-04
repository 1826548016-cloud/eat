import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from .user_moderation import can_user_login, get_user_profile, is_account_banned

User = get_user_model()

AUD_USER = 'gfqbj-user'
AUD_ADMIN = 'gfqbj-admin'
TYP_ACCESS = 'access'
TYP_REFRESH = 'refresh'

USER_ACCESS_COOKIE = 'gfqbj_access'
USER_REFRESH_COOKIE = 'gfqbj_refresh'
ADMIN_ACCESS_COOKIE = 'gfqbj_admin_access'
ADMIN_REFRESH_COOKIE = 'gfqbj_admin_refresh'

AUDIENCE_CONFIG = {
    AUD_USER: {
        'access_cookie': USER_ACCESS_COOKIE,
        'refresh_cookie': USER_REFRESH_COOKIE,
    },
    AUD_ADMIN: {
        'access_cookie': ADMIN_ACCESS_COOKIE,
        'refresh_cookie': ADMIN_REFRESH_COOKIE,
    },
}


class JwtAuthError(Exception):
    def __init__(self, code, message=''):
        self.code = code
        self.message = message
        super().__init__(message or code)


def _now():
    return datetime.now(dt_timezone.utc)


def _jwt_settings():
    return {
        'secret': getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY),
        'algorithm': getattr(settings, 'JWT_ALGORITHM', 'HS256'),
        'issuer': getattr(settings, 'JWT_ISSUER', 'gfqbj'),
        'access_ttl': getattr(settings, 'JWT_ACCESS_TTL', timedelta(minutes=15)),
        'refresh_ttl': getattr(settings, 'JWT_REFRESH_TTL', timedelta(days=7)),
        'leeway': getattr(settings, 'JWT_LEEWAY_SECONDS', 0),
    }


def bump_auth_token_version(user):
    from .models import UserProfile

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.auth_token_version = (profile.auth_token_version or 0) + 1
    profile.save(update_fields=['auth_token_version'])
    return profile.auth_token_version


def _build_payload(*, user, audience, token_type, token_version, ttl):
    cfg = _jwt_settings()
    now = _now()
    payload = {
        'iss': cfg['issuer'],
        'aud': audience,
        'sub': str(user.id),
        'typ': token_type,
        'ver': token_version,
        'iat': now,
        'nbf': now,
        'exp': now + ttl,
    }
    if token_type == TYP_REFRESH:
        payload['jti'] = uuid.uuid4().hex
    return payload


def _encode(payload):
    cfg = _jwt_settings()
    return jwt.encode(payload, cfg['secret'], algorithm=cfg['algorithm'])


def _decode(token, *, audience, token_type):
    cfg = _jwt_settings()
    try:
        payload = jwt.decode(
            token,
            cfg['secret'],
            algorithms=[cfg['algorithm']],
            audience=audience,
            issuer=cfg['issuer'],
            leeway=cfg['leeway'],
            options={
                'require': ['exp', 'iat', 'nbf', 'sub', 'typ', 'aud', 'iss', 'ver'],
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise JwtAuthError('expired', '令牌已过期') from exc
    except jwt.InvalidTokenError as exc:
        raise JwtAuthError('invalid', '令牌无效') from exc

    if payload.get('typ') != token_type:
        raise JwtAuthError('invalid_type', '令牌类型错误')
    return payload


def _load_user(payload, *, audience):
    try:
        user_id = int(payload['sub'])
    except (TypeError, ValueError) as exc:
        raise JwtAuthError('invalid', '令牌主体无效') from exc

    user = User.objects.filter(id=user_id).first()
    if not user or not user.is_active:
        raise JwtAuthError('invalid_user', '用户不存在或已停用')

    profile = get_user_profile(user)
    if payload.get('ver') != profile.auth_token_version:
        raise JwtAuthError('revoked', '登录状态已失效，请重新登录')

    if audience == AUD_USER and not user.is_staff:
        if is_account_banned(profile, user):
            raise JwtAuthError('banned', '账号已被封禁')
        allowed, _ = can_user_login(user)
        if not allowed:
            raise JwtAuthError('restricted', '账号已被限制登录')

    if audience == AUD_ADMIN and not user.is_staff:
        if not user.is_staff:
            raise JwtAuthError('not_staff', '无管理员权限')

    return user


def issue_token_pair(user, *, audience, bump_version=False):
    profile = get_user_profile(user)
    if bump_version:
        token_version = bump_auth_token_version(user)
    else:
        token_version = profile.auth_token_version or 0

    cfg = _jwt_settings()
    access = _encode(_build_payload(
        user=user,
        audience=audience,
        token_type=TYP_ACCESS,
        token_version=token_version,
        ttl=cfg['access_ttl'],
    ))
    refresh = _encode(_build_payload(
        user=user,
        audience=audience,
        token_type=TYP_REFRESH,
        token_version=token_version,
        ttl=cfg['refresh_ttl'],
    ))
    return {'access': access, 'refresh': refresh}


def verify_access_token(token, *, audience):
    payload = _decode(token, audience=audience, token_type=TYP_ACCESS)
    return _load_user(payload, audience=audience)


def verify_refresh_token(token, *, audience):
    payload = _decode(token, audience=audience, token_type=TYP_REFRESH)
    return _load_user(payload, audience=audience)


def _cookie_base(max_age):
    secure = getattr(settings, 'JWT_COOKIE_SECURE', not settings.DEBUG)
    return {
        'httponly': True,
        'secure': secure,
        'samesite': 'Lax',
        'max_age': max_age,
    }


def set_auth_cookies(response, tokens, *, audience):
    cfg = _jwt_settings()
    meta = AUDIENCE_CONFIG[audience]
    response.set_cookie(
        meta['access_cookie'],
        tokens['access'],
        path='/',
        **_cookie_base(int(cfg['access_ttl'].total_seconds())),
    )
    response.set_cookie(
        meta['refresh_cookie'],
        tokens['refresh'],
        path='/',
        samesite='Strict',
        httponly=True,
        secure=getattr(settings, 'JWT_COOKIE_SECURE', not settings.DEBUG),
        max_age=int(cfg['refresh_ttl'].total_seconds()),
    )


def clear_auth_cookies(response, *, audience):
    meta = AUDIENCE_CONFIG[audience]
    response.delete_cookie(meta['access_cookie'], path='/')
    response.delete_cookie(meta['refresh_cookie'], path='/')


def clear_all_auth_cookies(response):
    clear_auth_cookies(response, audience=AUD_USER)
    clear_auth_cookies(response, audience=AUD_ADMIN)


def get_access_token(request, *, audience):
    meta = AUDIENCE_CONFIG[audience]
    return request.COOKIES.get(meta['access_cookie'])


def get_refresh_token(request, *, audience):
    meta = AUDIENCE_CONFIG[audience]
    return request.COOKIES.get(meta['refresh_cookie'])


def authenticate_request(request, *, audience):
    access = get_access_token(request, audience=audience)
    if access:
        try:
            return verify_access_token(access, audience=audience), None
        except JwtAuthError as exc:
            if exc.code != 'expired':
                return AnonymousUser(), exc

    refresh = get_refresh_token(request, audience=audience)
    if not refresh:
        return AnonymousUser(), JwtAuthError('missing', '未登录') if access else None

    try:
        user = verify_refresh_token(refresh, audience=audience)
    except JwtAuthError as exc:
        return AnonymousUser(), exc

    tokens = issue_token_pair(user, audience=audience)
    return user, {'tokens': tokens, 'audience': audience}


def verify_access_from_request(request, *, audience):
    access = get_access_token(request, audience=audience)
    if not access:
        return None
    try:
        return verify_access_token(access, audience=audience)
    except JwtAuthError:
        return None


def is_admin_jwt_authenticated(request):
    return verify_access_from_request(request, audience=AUD_ADMIN) is not None


def authenticate_user_request(request):
    """前台路由：优先 user JWT；已登录管理后台的 staff 也可操作前台。"""
    user, meta = authenticate_request(request, audience=AUD_USER)
    if user.is_authenticated:
        return user, meta
    user_error = meta if isinstance(meta, JwtAuthError) else None
    admin_user, admin_meta = authenticate_request(request, audience=AUD_ADMIN)
    if admin_user.is_authenticated and admin_user.is_staff:
        return admin_user, admin_meta
    return user, user_error or admin_meta


def authenticate_admin_request(request):
    """后台路由：优先 admin JWT；若无则允许 staff 的前台 JWT 并补发 admin Cookie。"""
    user, meta = authenticate_request(request, audience=AUD_ADMIN)
    if user.is_authenticated:
        return user, meta

    admin_error = meta if isinstance(meta, JwtAuthError) else None
    user, user_meta = authenticate_request(request, audience=AUD_USER)
    if user.is_authenticated and user.is_staff:
        pending = [{
            'tokens': issue_token_pair(user, audience=AUD_ADMIN),
            'audience': AUD_ADMIN,
        }]
        if isinstance(user_meta, dict) and user_meta.get('tokens'):
            pending.append(user_meta)
        return user, pending[0] if len(pending) == 1 else pending

    return AnonymousUser(), admin_error or user_meta


def apply_pending_auth(response, request):
    pending_list = getattr(request, '_jwt_pending_auth_list', None)
    if pending_list:
        for item in pending_list:
            set_auth_cookies(response, item['tokens'], audience=item['audience'])
    pending = getattr(request, '_jwt_pending_auth', None)
    if pending:
        set_auth_cookies(response, pending['tokens'], audience=pending['audience'])
    revoke = getattr(request, '_jwt_revoke_auth', None)
    if revoke:
        clear_auth_cookies(response, audience=revoke)


def login_with_jwt(request, user, *, audience, bump_version=True):
    from django.contrib.auth import logout as auth_logout

    auth_logout(request)
    tokens = issue_token_pair(user, audience=audience, bump_version=bump_version)
    request._jwt_pending_auth = {'tokens': tokens, 'audience': audience}
    request.user = user
    return tokens


def login_staff_with_jwt(request, user, *, bump_version=True):
    """管理员/staff 登录：同时签发前台与后台 JWT，避免 Cookie 受众不一致。"""
    from django.contrib.auth import logout as auth_logout

    auth_logout(request)
    tokens_user = issue_token_pair(user, audience=AUD_USER, bump_version=bump_version)
    tokens_admin = issue_token_pair(user, audience=AUD_ADMIN, bump_version=False)
    request._jwt_pending_auth_list = [
        {'tokens': tokens_user, 'audience': AUD_USER},
        {'tokens': tokens_admin, 'audience': AUD_ADMIN},
    ]
    request.user = user
    return tokens_user, tokens_admin


def logout_with_jwt(request, *, audience=None):
    from django.contrib.auth import logout as auth_logout

    auth_logout(request)
    request.user = AnonymousUser()
    if audience:
        request._jwt_revoke_auth = audience
    else:
        request._jwt_revoke_all = True


def finalize_jwt_response(response, request):
    if getattr(request, '_jwt_revoke_all', False):
        clear_all_auth_cookies(response)
    elif getattr(request, '_jwt_revoke_auth', None):
        clear_auth_cookies(response, audience=request._jwt_revoke_auth)
    apply_pending_auth(response, request)
    return response

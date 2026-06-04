import secrets

from django.core import signing

from .models import SiteConfig

BETA_COOKIE_NAME = 'beta_access'
BETA_SIGNER_SALT = 'lunch-beta-access'
BETA_COOKIE_MAX_AGE = 30 * 24 * 3600


def _get_signer():
    return signing.TimestampSigner(salt=BETA_SIGNER_SALT)


def is_beta_mode():
    return SiteConfig.get_singleton().is_beta_mode


def generate_invite_code(length=8):
    return secrets.token_hex(length // 2).upper()[:length]


def check_invite_code(code, config=None):
    if config is None:
        config = SiteConfig.get_singleton()
    if not config.beta_invite_code:
        return False
    entered = (code or '').strip().upper()
    expected = config.beta_invite_code.strip().upper()
    return bool(entered) and entered == expected


def _sign_revision(revision):
    return _get_signer().sign(str(revision))


def has_beta_access(request, config=None):
    if config is None:
        config = SiteConfig.get_singleton()
    if not config.is_beta_mode:
        return True
    if getattr(request.user, 'is_staff', False):
        return True
    token = request.COOKIES.get(BETA_COOKIE_NAME)
    if not token:
        return False
    try:
        value = _get_signer().unsign(token, max_age=BETA_COOKIE_MAX_AGE)
        return value == str(config.beta_code_revision)
    except (signing.SignatureExpired, signing.BadSignature, ValueError):
        # ValueError: 旧版 Signer 签名的 Cookie 与 TimestampSigner 不兼容
        return False


def grant_beta_access(response, config=None):
    if config is None:
        config = SiteConfig.get_singleton()
    response.set_cookie(
        BETA_COOKIE_NAME,
        _sign_revision(config.beta_code_revision),
        max_age=BETA_COOKIE_MAX_AGE,
        httponly=True,
        samesite='Lax',
    )
    return response


def clear_beta_access(response):
    response.delete_cookie(BETA_COOKIE_NAME)
    return response


def ensure_beta_code(config=None):
    """开启内测前确保已有邀请码。"""
    if config is None:
        config = SiteConfig.get_singleton()
    if not config.beta_invite_code:
        config.beta_invite_code = generate_invite_code()
        config.beta_code_revision += 1
        config.save(update_fields=['beta_invite_code', 'beta_code_revision'])
    return config

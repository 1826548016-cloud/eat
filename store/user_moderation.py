from .models import UserProfile


def get_user_profile(user):
    if not user or not user.is_authenticated:
        return None
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def is_account_banned(profile, user):
    return profile.is_banned or not user.is_active


def can_user_login(user):
    """前台登录校验。管理员走后台登录，不在此限制。"""
    if user.is_staff:
        return True, ''
    profile = get_user_profile(user)
    if is_account_banned(profile, user):
        return False, '该账号已被封禁，无法登录'
    if profile.login_restricted:
        return False, '该账号已被限制登录，请联系管理员'
    return True, ''


def can_user_post(user):
    """发帖、评论校验。"""
    if not user.is_authenticated:
        return False, '请先登录'
    if user.is_staff:
        return True, ''
    profile = get_user_profile(user)
    if is_account_banned(profile, user):
        return False, '账号已被封禁'
    if profile.is_muted:
        return False, '您已被禁言，暂不可发帖或评论'
    return True, ''


def punishment_labels(profile):
    """返回当前处罚状态标签列表。"""
    labels = []
    if profile.is_banned:
        labels.append('封号')
    if profile.is_muted:
        labels.append('禁言')
    if profile.login_restricted:
        labels.append('限制登录')
    return labels

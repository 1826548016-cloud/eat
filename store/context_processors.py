from .models import Announcement
from .beta_access import is_beta_mode
from .site_config import get_site_config, is_site_open, closed_message
from .contact_info import has_contact_info

VALID_THEMES = ('light', 'dark')


def site_announcements(request):
    return {
        'site_announcements': Announcement.objects.filter(is_active=True).select_related('author')[:5],
    }


def site_preferences(request):
    theme = request.COOKIES.get('site_theme', '')
    if theme not in VALID_THEMES:
        theme = 'light'
    ctx = {
        'site_theme': theme,
        'html_lang': 'zh-CN',
        'site_name': '干饭情报局',
        'site_is_open': is_site_open(),
        'site_config': get_site_config(),
        'site_closed_message': closed_message(),
        'is_beta_mode': is_beta_mode(),
        'has_contact_info': has_contact_info(get_site_config()),
    }
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        profile = getattr(user, 'profile', None)
        if profile is None:
            from .models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
        ctx['user_avatar_url'] = profile.avatar.url if profile.avatar else ''
        # Unread notification count
        from .models import Notification
        ctx['unread_notification_count'] = Notification.objects.filter(
            recipient=user, is_read=False,
        ).count()
        if user.is_staff:
            from .models import ContentReport
            ctx['admin_pending_reports'] = ContentReport.objects.filter(
                status=ContentReport.STATUS_PENDING,
            ).count()
    return ctx

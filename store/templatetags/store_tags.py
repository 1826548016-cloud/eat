from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def thumb_url(photo):
    """Return thumbnail URL for a PostImage, falling back to original."""
    if hasattr(photo, 'thumb_url'):
        return photo.thumb_url()
    if hasattr(photo, 'thumbnail') and photo.thumbnail:
        return photo.thumbnail.url
    return photo.image.url if photo.image else ''


@register.filter
def cover_thumb(post):
    """Return cover thumbnail URL for a LunchPost (card/list views)."""
    if hasattr(post, 'cover_thumb_url'):
        url = post.cover_thumb_url
        if url:
            return url
    if hasattr(post, 'cover_image') and post.cover_image:
        return post.cover_image.url
    return ''


@register.filter
def user_avatar(user):
    """Return avatar URL for a User object, or empty string."""
    profile = getattr(user, 'profile', None)
    if profile and hasattr(profile, 'avatar_url'):
        return profile.avatar_url()
    if profile and profile.avatar:
        return profile.avatar.url
    return ''


@register.simple_tag
def avatar_or_initial(user, size=32):
    """Return HTML for avatar image or initial letter placeholder."""
    profile = getattr(user, 'profile', None)
    has_avatar = profile and profile.avatar
    initial = (user.username or '?')[0].upper()
    if has_avatar:
        return mark_safe(
            f'<img src="{profile.avatar.url}" alt="{user.username}" '
            f'class="avatar avatar--{size}" width="{size}" height="{size}" loading="lazy">'
        )
    return mark_safe(
        f'<span class="avatar avatar--placeholder avatar--{size}" '
        f'style="width:{size}px;height:{size}px;">{initial}</span>'
    )

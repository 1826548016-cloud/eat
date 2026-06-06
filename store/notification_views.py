"""通知中心：消息列表、标记已读、未读数 API。"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Notification


def create_notification(*, recipient, actor, notif_type, post=None, comment=None):
    """Create a notification unless recipient == actor or a duplicate exists."""
    if recipient.id == actor.id:
        return None
    # Avoid duplicate unread notifications for the same actor/target
    if Notification.objects.filter(
        recipient=recipient,
        actor=actor,
        notif_type=notif_type,
        post=post,
        comment=comment,
        is_read=False,
    ).exists():
        return None
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notif_type=notif_type,
        post=post,
        comment=comment,
    )


@login_required
def notification_list(request):
    qs = (
        Notification.objects.filter(recipient=request.user)
        .select_related('actor', 'actor__profile', 'post', 'comment')
        .order_by('-created_at')
    )
    unread_count = qs.filter(is_read=False).count()
    notifications = qs[:80]
    return render(request, 'store/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
def mark_read(request, notification_id):
    if request.method != 'POST':
        return redirect('notification_list')
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    # Redirect to the post if available
    if notif.post:
        return redirect('post_detail', post_id=notif.post.id)
    return redirect('notification_list')


@login_required
def mark_all_read(request):
    if request.method != 'POST':
        return redirect('notification_list')
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect('notification_list')


@login_required
def unread_count_api(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'unread': count})

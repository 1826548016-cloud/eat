"""社区功能：编辑、收藏、举报、申诉、后台处理。"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .admin_access import is_admin, is_super_admin, super_admin_required
from .audit import log_operation
from .jwt_auth import bump_auth_token_version
from .models import (
    Comment, ContentReport, FoodCategory, LunchPost, OperationLog,
    PostFavorite, UserProfile,
)
from .post_forms import apply_post_form, validate_post_form
from .post_media import MAX_FOOD_PHOTOS
from .rate_limit import check_rate_limit, hit_rate_limit


def _handle_report(request, *, post=None, comment=None):
    if not request.user.is_authenticated:
        return redirect('user_login')
    allowed, rl_msg = check_rate_limit(request.user, 'report')
    if not allowed:
        messages.error(request, rl_msg)
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
        return redirect(next_url if next_url.startswith('/') else '/')
    reason = request.POST.get('reason', '')
    detail = request.POST.get('detail', '').strip()[:1000]
    valid_reasons = {c[0] for c in ContentReport.REASON_CHOICES}
    if reason not in valid_reasons:
        messages.error(request, '请选择举报原因')
    elif post:
        pending = ContentReport.objects.filter(
            reporter=request.user,
            post=post,
            report_type=ContentReport.TYPE_POST,
            status=ContentReport.STATUS_PENDING,
        ).exists()
        if pending:
            messages.error(request, '您已举报过该内容，请等待管理员处理')
        else:
            ContentReport.objects.create(
                report_type=ContentReport.TYPE_POST,
                reporter=request.user,
                post=post,
                reason=reason,
                detail=detail,
            )
            hit_rate_limit(request.user, 'report')
            log_operation(
                request, OperationLog.ACTION_REPORT_CREATE, user=request.user,
                detail=f'举报推荐《{post.title}》',
                target_type='post', target_id=post.id,
            )
            messages.success(request, '举报已提交，管理员会尽快处理')
    elif comment:
        pending = ContentReport.objects.filter(
            reporter=request.user,
            comment=comment,
            report_type=ContentReport.TYPE_COMMENT,
            status=ContentReport.STATUS_PENDING,
        ).exists()
        if pending:
            messages.error(request, '您已举报过该评论')
        else:
            ContentReport.objects.create(
                report_type=ContentReport.TYPE_COMMENT,
                reporter=request.user,
                post=comment.post,
                comment=comment,
                reason=reason,
                detail=detail,
            )
            hit_rate_limit(request.user, 'report')
            log_operation(
                request, OperationLog.ACTION_REPORT_CREATE, user=request.user,
                detail=f'举报评论 #{comment.id}',
                target_type='comment', target_id=comment.id,
            )
            messages.success(request, '举报已提交')
    next_url = request.POST.get('next') or (
        reverse_post_detail(post) if post else reverse_post_detail(comment.post)
    )
    return redirect(next_url)


def reverse_post_detail(post):
    from django.urls import reverse
    return reverse('post_detail', kwargs={'post_id': post.id})


@login_required
def post_edit(request, post_id):
    from .user_moderation import can_user_post

    post = get_object_or_404(
        LunchPost.objects.prefetch_related('photos'),
        id=post_id,
    )
    if post.author != request.user and not request.user.is_staff:
        messages.error(request, '只能编辑自己发布的内容')
        return redirect('post_detail', post_id=post.id)
    ok, msg = can_user_post(request.user)
    if not ok and post.author == request.user:
        messages.error(request, msg)
        return redirect('post_detail', post_id=post.id)
    categories = FoodCategory.objects.all()
    ctx = {'categories': categories, 'post': post, 'is_edit': True, 'max_photos': MAX_FOOD_PHOTOS}
    if request.method == 'POST':
        allowed, rl_msg = check_rate_limit(request.user, 'post_edit')
        if not allowed:
            messages.error(request, rl_msg)
            return render(request, 'store/post_form.html', ctx)
        data, err = validate_post_form(request)
        if err:
            messages.error(request, err)
            return render(request, 'store/post_form.html', ctx)
        remove_ids = [int(x) for x in data['remove_photo_ids'] if str(x).isdigit()]
        existing_count = post.photos.count() - len(remove_ids)
        if existing_count + len(data['food_files']) > MAX_FOOD_PHOTOS:
            messages.error(request, f'实拍图最多 {MAX_FOOD_PHOTOS} 张')
            return render(request, 'store/post_form.html', ctx)
        apply_post_form(post, data, is_new=False)
        hit_rate_limit(request.user, 'post_edit')
        log_operation(
            request, OperationLog.ACTION_POST_EDIT, user=request.user,
            detail=f'编辑《{post.title}》',
            target_type='post', target_id=post.id,
        )
        messages.success(request, '推荐已更新')
        return redirect('post_detail', post_id=post.id)
    return render(request, 'store/post_form.html', ctx)


@login_required
def user_favorites(request):
    favorites = (
        PostFavorite.objects.filter(user=request.user)
        .select_related('post', 'post__category', 'post__author')
        .prefetch_related('post__photos')
        .order_by('-created_at')
    )
    return render(request, 'store/favorites.html', {'favorites': favorites})


@login_required
def report_comment(request, comment_id):
    if request.method != 'POST':
        return redirect('index')
    comment = get_object_or_404(Comment.objects.select_related('post'), id=comment_id)
    return _handle_report(request, comment=comment)


@user_passes_test(is_admin, login_url='admin_login')
def admin_post_edit(request, post_id):
    post = get_object_or_404(
        LunchPost.objects.prefetch_related('photos').select_related('category', 'author'),
        id=post_id,
    )
    categories = FoodCategory.objects.all()
    ctx = {'post': post, 'categories': categories, 'section': 'posts', 'is_edit': True, 'max_photos': MAX_FOOD_PHOTOS}
    if request.method == 'POST':
        data, err = validate_post_form(request)
        if err:
            messages.error(request, err)
            return render(request, 'admin/post_edit.html', ctx)
        remove_ids = [int(x) for x in data['remove_photo_ids'] if str(x).isdigit()]
        existing_count = post.photos.count() - len(remove_ids)
        if existing_count + len(data['food_files']) > MAX_FOOD_PHOTOS:
            messages.error(request, f'实拍图最多 {MAX_FOOD_PHOTOS} 张')
            return render(request, 'admin/post_edit.html', ctx)
        apply_post_form(post, data, is_new=False)
        log_operation(
            request, OperationLog.ACTION_ADMIN_POST_EDIT, user=request.user,
            detail=f'管理员编辑《{post.title}》',
            target_type='post', target_id=post.id,
        )
        messages.success(request, '推荐已更新')
        return redirect('admin_post_list')
    return render(request, 'admin/post_edit.html', ctx)


@user_passes_test(is_admin, login_url='admin_login')
def admin_report_list(request):
    status = request.GET.get('status', ContentReport.STATUS_PENDING)
    reports = ContentReport.objects.select_related(
        'reporter', 'post', 'post__author', 'post__author__profile',
        'comment', 'comment__user', 'comment__user__profile', 'handled_by',
    )
    if status != 'all':
        reports = reports.filter(status=status)
    pending_count = ContentReport.objects.filter(status=ContentReport.STATUS_PENDING).count()
    return render(request, 'admin/report_list.html', {
        'reports': reports[:100],
        'status': status,
        'pending_count': pending_count,
        'section': 'reports',
    })


@user_passes_test(is_admin, login_url='admin_login')
def admin_report_handle(request, report_id):
    if request.method != 'POST':
        return redirect('admin_report_list')
    report = get_object_or_404(ContentReport, id=report_id)
    action = request.POST.get('action')
    note = request.POST.get('admin_note', '').strip()[:500]
    if action == 'resolve':
        report.status = ContentReport.STATUS_RESOLVED
    elif action == 'dismiss':
        report.status = ContentReport.STATUS_DISMISSED
    else:
        messages.error(request, '无效操作')
        return redirect('admin_report_list')
    report.admin_note = note
    report.handled_by = request.user
    report.handled_at = timezone.now()
    report.save()
    log_operation(
        request, OperationLog.ACTION_ADMIN_REPORT_HANDLE, user=request.user,
        detail=f'{report.get_status_display()} · {report.get_report_type_display()} #{report.id}',
        target_type='report', target_id=report.id,
    )
    messages.success(request, '处理结果已保存')
    return redirect('admin_report_list')


@super_admin_required
def admin_staff_list(request):
    return render(request, 'admin/staff_list.html', {
        'staff_users': User.objects.filter(is_staff=True).order_by('-is_superuser', '-date_joined'),
        'section': 'staff',
    })


@super_admin_required
def admin_staff_create(request):
    if request.method != 'POST':
        return redirect('admin_staff_list')
    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '').strip()
    password2 = request.POST.get('password2', '').strip()
    email = request.POST.get('email', '').strip()
    if not username:
        messages.error(request, '请填写用户名')
        return redirect('admin_staff_list')
    if User.objects.filter(username=username).exists():
        messages.error(request, '用户名已存在')
        return redirect('admin_staff_list')
    if len(password) < 4:
        messages.error(request, '密码至少4位')
        return redirect('admin_staff_list')
    if password != password2:
        messages.error(request, '两次密码不一致')
        return redirect('admin_staff_list')
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        is_staff=True,
        is_superuser=False,
    )
    UserProfile.objects.create(user=user)
    log_operation(
        request, OperationLog.ACTION_ADMIN_STAFF_CREATE, user=request.user,
        detail=f'创建普通管理员 {username}',
        target_type='user', target_id=user.id,
    )
    messages.success(request, f'已创建普通管理员 {username}')
    return redirect('admin_staff_list')


@super_admin_required
def admin_staff_remove(request, user_id):
    if request.method != 'POST':
        return redirect('admin_staff_list')
    target = get_object_or_404(User, id=user_id)
    if target.id == request.user.id:
        messages.error(request, '不能移除自己的管理员权限')
        return redirect('admin_staff_list')
    if target.is_superuser:
        messages.error(request, '不能移除超级管理员权限')
        return redirect('admin_staff_list')
    if not target.is_staff:
        messages.error(request, '该用户不是管理员')
        return redirect('admin_staff_list')
    target.is_staff = False
    target.save(update_fields=['is_staff'])
    bump_auth_token_version(target)
    log_operation(
        request, OperationLog.ACTION_ADMIN_STAFF_REMOVE, user=request.user,
        detail=f'移除普通管理员 {target.username}',
        target_type='user', target_id=target.id,
    )
    messages.success(request, f'已移除 {target.username} 的管理员权限')
    return redirect('admin_staff_list')


@super_admin_required
def admin_staff_reset_password(request, user_id):
    if request.method != 'POST':
        return redirect('admin_staff_list')
    target = get_object_or_404(User, id=user_id)
    if not target.is_staff:
        messages.error(request, '该用户不是管理员')
        return redirect('admin_staff_list')
    if target.is_superuser:
        messages.error(request, '超级管理员请在个人中心修改密码')
        return redirect('admin_staff_list')
    new_password = request.POST.get('new_password', '').strip()
    confirm = request.POST.get('new_password2', '').strip()
    if len(new_password) < 4:
        messages.error(request, '新密码至少4位')
        return redirect('admin_staff_list')
    if new_password != confirm:
        messages.error(request, '两次密码不一致')
        return redirect('admin_staff_list')
    target.set_password(new_password)
    target.save(update_fields=['password'])
    bump_auth_token_version(target)
    log_operation(
        request, OperationLog.ACTION_ADMIN_STAFF_RESET_PASSWORD, user=request.user,
        detail=f'重置管理员 {target.username} 的密码',
        target_type='user', target_id=target.id,
    )
    messages.success(request, f'已重置管理员 {target.username} 的密码')
    return redirect('admin_staff_list')

import json
import random

from urllib.parse import unquote, urlparse

from django.http import JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, F, Q
from .models import (
    UserProfile, FoodCategory, LunchPost, PostImage, PostView, Comment,
    Announcement, FriendLink, SiteConfig, LoginLog, OperationLog,
    ContentReport, PostFavorite, PostEndorsement, Notification,
)
from .audit import log_login, log_operation
from .admin_access import is_admin, is_super_admin
from .site_config import is_site_open, get_contact_context
from .beta_access import (
    is_beta_mode, check_invite_code, has_beta_access, grant_beta_access,
    generate_invite_code, ensure_beta_code,
)
from .user_moderation import can_user_login, can_user_post
from .post_media import MAX_FOOD_PHOTOS, compress_avatar
from .post_forms import validate_post_form, apply_post_form
from .rate_limit import check_rate_limit, hit_rate_limit
from .stats import get_dashboard_stats, get_home_chart_data
from .social_views import _handle_report
from .notification_views import create_notification
from .jwt_auth import (
    AUD_ADMIN,
    AUD_USER,
    JwtAuthError,
    bump_auth_token_version,
    get_refresh_token,
    is_admin_jwt_authenticated,
    issue_token_pair,
    login_staff_with_jwt,
    login_with_jwt,
    logout_with_jwt,
    verify_refresh_token,
)
from django.utils import timezone


def set_preferences(request):
    next_url = unquote(request.GET.get('next', '') or '/')
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = '/'
    theme = request.GET.get('theme', '')
    cookie_age = 365 * 24 * 3600
    if theme in ('light', 'dark') and request.GET.get('ajax') == '1':
        response = JsonResponse({'ok': True, 'theme': theme})
        response.set_cookie('site_theme', theme, max_age=cookie_age, samesite='Lax')
        return response
    response = redirect(next_url)
    if theme in ('light', 'dark'):
        response.set_cookie('site_theme', theme, max_age=cookie_age, samesite='Lax')
    return response


def maintenance(request):
    return render(request, 'store/maintenance.html')


def beta_gate(request):
    if not is_beta_mode():
        return redirect('index')
    if has_beta_access(request):
        return redirect(request.GET.get('next', 'index'))
    error = ''
    if request.method == 'POST':
        code = request.POST.get('invite_code', '')
        config = ensure_beta_code()
        if check_invite_code(code, config):
            next_url = request.POST.get('next') or request.GET.get('next') or '/'
            if not url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                next_url = '/'
            response = redirect(next_url)
            grant_beta_access(response, config)
            return response
        error = 'invalid'
    return render(request, 'store/beta_gate.html', {
        'error': error,
        'next': request.GET.get('next', '/'),
    })


def index(request):
    posts = LunchPost.objects.select_related('category', 'author', 'author__profile').prefetch_related('photos').annotate(
        comment_count=Count('comments'),
        endorse_count=Count('endorsements'),
    ).order_by('-created_at')[:12]
    categories = FoodCategory.objects.all()
    today_pick = LunchPost.objects.order_by('?').first()
    return render(request, 'store/index.html', {
        'posts': posts,
        'categories': categories,
        'today_pick': today_pick,
        'total_posts': LunchPost.objects.count(),
        'chart_data': get_home_chart_data(),
    })


def disclaimer(request):
    return render(request, 'store/disclaimer.html')


def contact_admin(request):
    return render(request, 'store/contact.html', get_contact_context())


def friend_links(request):
    config = SiteConfig.get_singleton()
    links = FriendLink.objects.filter(is_active=True).order_by('sort_order', '-created_at')
    return render(request, 'store/friend_links.html', {
        'links': links,
        'page_intro': config.friend_links_intro,
    })


def _normalize_link_url(url):
    url = (url or '').strip()
    if url and not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


@user_passes_test(is_admin, login_url='admin_login')
def admin_contact(request):
    config = SiteConfig.get_singleton()
    if request.method == 'POST':
        config.contact_intro_zh = request.POST.get('contact_intro_zh', '').strip()
        config.contact_email = request.POST.get('contact_email', '').strip()
        config.contact_phone = request.POST.get('contact_phone', '').strip()[:30]
        config.contact_wechat = request.POST.get('contact_wechat', '').strip()[:80]
        config.contact_qq = request.POST.get('contact_qq', '').strip()[:30]
        config.contact_telegram = request.POST.get('contact_telegram', '').strip()[:80]
        config.contact_weibo = request.POST.get('contact_weibo', '').strip()
        config.contact_xiaohongshu = request.POST.get('contact_xiaohongshu', '').strip()
        config.contact_github = request.POST.get('contact_github', '').strip()
        config.contact_bilibili = request.POST.get('contact_bilibili', '').strip()
        config.updated_by = request.user
        config.save()
        log_operation(
            request, OperationLog.ACTION_ADMIN_CONTACT_UPDATE, user=request.user,
            detail='更新管理员联系方式',
        )
        messages.success(request, '联系方式已保存')
        return redirect('admin_contact')
    return render(request, 'admin/contact.html', {
        'site_config': config,
        'section': 'contact',
    })


@user_passes_test(is_admin, login_url='admin_login')
def admin_friend_link_list(request):
    config = SiteConfig.get_singleton()
    if request.method == 'POST' and request.POST.get('action') == 'update_intro':
        config.friend_links_intro = request.POST.get('friend_links_intro', '').strip()
        config.updated_by = request.user
        config.save()
        messages.success(request, '友链页说明已保存')
        return redirect('admin_friend_link_list')
    return render(request, 'admin/friend_link_list.html', {
        'links': FriendLink.objects.order_by('sort_order', '-created_at'),
        'site_config': config,
        'section': 'friend_links',
    })


@user_passes_test(is_admin, login_url='admin_login')
def admin_friend_link_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        url = _normalize_link_url(request.POST.get('url', ''))
        if not name or not url:
            messages.error(request, '站点名称和链接为必填项')
            return redirect('admin_friend_link_list')
        link = FriendLink.objects.create(
            name=name,
            url=url,
            description=request.POST.get('description', '').strip()[:200],
            icon=request.POST.get('icon', '🔗').strip()[:20] or '🔗',
            sort_order=int(request.POST.get('sort_order') or 0),
            is_active=request.POST.get('is_active') == '1',
        )
        log_operation(
            request, OperationLog.ACTION_ADMIN_FRIEND_LINK_ADD, user=request.user,
            detail=f'添加友链 {link.name}',
            target_type='friend_link', target_id=link.id,
        )
        messages.success(request, '友链已添加')
    return redirect('admin_friend_link_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_friend_link_edit(request, link_id):
    link = get_object_or_404(FriendLink, id=link_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        url = _normalize_link_url(request.POST.get('url', ''))
        if not name or not url:
            messages.error(request, '站点名称和链接为必填项')
            return redirect('admin_friend_link_list')
        link.name = name
        link.url = url
        link.description = request.POST.get('description', '').strip()[:200]
        link.icon = request.POST.get('icon', '🔗').strip()[:20] or '🔗'
        link.sort_order = int(request.POST.get('sort_order') or 0)
        link.is_active = request.POST.get('is_active') == '1'
        link.save()
        log_operation(
            request, OperationLog.ACTION_ADMIN_FRIEND_LINK_EDIT, user=request.user,
            detail=f'编辑友链 {link.name}',
            target_type='friend_link', target_id=link.id,
        )
        messages.success(request, '友链已更新')
    return redirect('admin_friend_link_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_friend_link_delete(request, link_id):
    link = get_object_or_404(FriendLink, id=link_id)
    log_operation(
        request, OperationLog.ACTION_ADMIN_FRIEND_LINK_DELETE, user=request.user,
        detail=f'删除友链 {link.name}',
        target_type='friend_link', target_id=link.id,
    )
    link.delete()
    messages.success(request, '友链已删除')
    return redirect('admin_friend_link_list')


def lunch_wheel(request):
    posts = list(
        LunchPost.objects.values('id', 'title', 'location', 'price'),
    )
    if len(posts) > 10:
        posts = random.sample(posts, 10)
    return render(request, 'store/wheel.html', {
        'wheel_items': posts,
        'wheel_items_json': json.dumps(posts, ensure_ascii=False),
        'item_count': len(posts),
    })


def incentive(request):
    total_posts = LunchPost.objects.count()
    total_endorsements = PostEndorsement.objects.count()
    total_users = User.objects.filter(is_staff=False).count()

    top_posts = LunchPost.objects.select_related('author').annotate(
        endorse_count=Count('endorsements'),
    ).filter(endorse_count__gt=0).order_by('-endorse_count')[:20]

    top_authors = (
        User.objects.filter(is_staff=False, lunch_posts__isnull=False)
        .annotate(
            total_posts=Count('lunch_posts', distinct=True),
            endorse_received=Count('lunch_posts__endorsements', distinct=True),
        )
        .filter(endorse_received__gt=0)
        .order_by('-endorse_received')[:20]
    )

    user_stats = None
    if request.user.is_authenticated:
        my_posts = LunchPost.objects.filter(author=request.user).annotate(
            endorse_count=Count('endorsements'),
        ).order_by('-endorse_count')
        total_views = sum(p.view_count for p in my_posts)
        total_post_count = len(my_posts)
        total_endorse_received = sum(p.endorse_count for p in my_posts)
        top_my_post = my_posts.first()
        user_stats = {
            'post_count': total_post_count,
            'endorse_received': total_endorse_received,
            'total_views': total_views,
            'top_post': top_my_post,
        }

    return render(request, 'store/incentive.html', {
        'total_posts': total_posts,
        'total_endorsements': total_endorsements,
        'total_users': total_users,
        'top_posts': top_posts,
        'top_authors': top_authors,
        'user_stats': user_stats,
    })


def post_list(request):
    category_id = request.GET.get('category', '')
    keyword = request.GET.get('q', '')
    posts = LunchPost.objects.select_related('category', 'author', 'author__profile').prefetch_related('photos').annotate(
        comment_count=Count('comments'),
        endorse_count=Count('endorsements'),
    )
    if category_id:
        posts = posts.filter(category_id=category_id)
    if keyword:
        posts = posts.filter(
            Q(title__icontains=keyword)
            | Q(location__icontains=keyword)
            | Q(description__icontains=keyword),
        )
    posts = posts.order_by('-created_at')
    return render(request, 'store/post_list.html', {
        'posts': posts,
        'categories': FoodCategory.objects.all(),
        'category_id': category_id,
        'keyword': keyword,
    })


def _record_post_view(post, user):
    _, created = PostView.objects.get_or_create(post=post, user=user)
    if created:
        LunchPost.objects.filter(pk=post.pk).update(view_count=F('view_count') + 1)
        post.view_count += 1


def post_detail(request, post_id):
    post = get_object_or_404(
        LunchPost.objects.select_related('category', 'author', 'author__profile').prefetch_related('photos').annotate(
            endorse_count=Count('endorsements'),
        ),
        id=post_id,
    )
    comments = post.comments.select_related('user', 'user__profile', 'parent', 'parent__user', 'parent__user__profile').order_by('created_at')
    if request.method == 'GET' and request.user.is_authenticated and not request.GET.get('posted'):
        _record_post_view(post, request.user)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, '请先登录')
            return redirect('user_login')
        action = request.POST.get('action', 'comment')
        if action == 'favorite':
            fav, created = PostFavorite.objects.get_or_create(user=request.user, post=post)
            if not created:
                fav.delete()
                messages.success(request, '已取消收藏')
            else:
                messages.success(request, '已加入想吃清单')
            return redirect('post_detail', post_id=post.id)
        if action == 'endorse':
            if post.author_id == request.user.id:
                messages.error(request, '不能推荐自己的分享')
                return redirect('post_detail', post_id=post.id)
            obj, created = PostEndorsement.objects.get_or_create(user=request.user, post=post)
            if not created:
                obj.delete()
                messages.success(request, '已取消推荐')
            else:
                create_notification(
                    recipient=post.author,
                    actor=request.user,
                    notif_type=Notification.TYPE_ENDORSE,
                    post=post,
                )
                messages.success(request, '感谢推荐，已计入首页统计')
            return redirect('post_detail', post_id=post.id)
        if action == 'report':
            return _handle_report(request, post=post)
        ok, msg = can_user_post(request.user)
        if not ok:
            messages.error(request, msg)
            return redirect('post_detail', post_id=post.id)
        allowed, rl_msg = check_rate_limit(request.user, 'comment')
        if not allowed:
            messages.error(request, rl_msg)
            return redirect('post_detail', post_id=post.id)
        content = request.POST.get('content', '').strip()
        parent = None
        parent_id = request.POST.get('parent_id', '').strip()
        if parent_id:
            parent = Comment.objects.filter(id=parent_id, post=post).first()
        if not content:
            messages.error(request, '评论不能为空')
        elif len(content) > 500:
            messages.error(request, '评论不能超过500字')
        else:
            new_comment = Comment.objects.create(post=post, user=request.user, content=content, parent=parent)
            hit_rate_limit(request.user, 'comment')
            log_operation(
                request, OperationLog.ACTION_COMMENT_CREATE, user=request.user,
                detail=f'评论《{post.title}》：{content[:80]}',
                target_type='post', target_id=post.id,
            )
            # Notify post author (comment on their post)
            if post.author_id != request.user.id:
                create_notification(
                    recipient=post.author,
                    actor=request.user,
                    notif_type=Notification.TYPE_COMMENT,
                    post=post,
                    comment=new_comment,
                )
            # Notify parent comment author (reply to their comment)
            if parent and parent.user_id != request.user.id and parent.user_id != post.author_id:
                create_notification(
                    recipient=parent.user,
                    actor=request.user,
                    notif_type=Notification.TYPE_REPLY,
                    post=post,
                    comment=new_comment,
                )
            messages.success(request, '评论成功')
            url = reverse('post_detail', kwargs={'post_id': post.id})
            return redirect(f'{url}?posted=1')
    is_favorited = (
        request.user.is_authenticated
        and PostFavorite.objects.filter(user=request.user, post=post).exists()
    )
    is_endorsed = (
        request.user.is_authenticated
        and PostEndorsement.objects.filter(user=request.user, post=post).exists()
    )
    can_post, mute_msg = can_user_post(request.user) if request.user.is_authenticated else (False, '')
    return render(request, 'store/post_detail.html', {
        'post': post,
        'comments': comments,
        'can_comment': can_post,
        'mute_message': mute_msg,
        'is_favorited': is_favorited,
        'is_endorsed': is_endorsed,
        'report_reasons': ContentReport.REASON_CHOICES,
    })


@login_required
def post_create(request):
    ok, msg = can_user_post(request.user)
    if not ok:
        messages.error(request, msg)
        return redirect('index')
    categories = FoodCategory.objects.all()
    if request.method == 'POST':
        if not request.POST.get('agree_disclaimer'):
            messages.error(request, '发布前请阅读并同意《免责声明与用户须知》')
            return render(request, 'store/post_form.html', {'categories': categories, 'max_photos': MAX_FOOD_PHOTOS})
        allowed, rl_msg = check_rate_limit(request.user, 'post_create')
        if not allowed:
            messages.error(request, rl_msg)
            return render(request, 'store/post_form.html', {'categories': categories, 'max_photos': MAX_FOOD_PHOTOS})
        data, err = validate_post_form(request)
        if err:
            messages.error(request, err)
            return render(request, 'store/post_form.html', {'categories': categories, 'max_photos': MAX_FOOD_PHOTOS})
        post = LunchPost(author=request.user)
        apply_post_form(post, data, is_new=True)
        hit_rate_limit(request.user, 'post_create')
        log_operation(
            request, OperationLog.ACTION_POST_CREATE, user=request.user,
            detail=f'发布《{post.title}》· {post.location}',
            target_type='post', target_id=post.id,
        )
        messages.success(request, '干饭情报发布成功，感谢分享！')
        return redirect('post_detail', post_id=post.id)
    return render(request, 'store/post_form.html', {'categories': categories, 'max_photos': MAX_FOOD_PHOTOS})


@login_required
def post_delete(request, post_id):
    if request.method != 'POST':
        return redirect('post_detail', post_id=post_id)
    post = get_object_or_404(LunchPost, id=post_id)
    if post.author != request.user and not request.user.is_staff:
        messages.error(request, '只能删除自己发布的内容')
        return redirect('post_detail', post_id=post_id)
    log_operation(
        request, OperationLog.ACTION_POST_DELETE, user=request.user,
        detail=f'删除《{post.title}》',
        target_type='post', target_id=post.id,
    )
    post.delete()
    messages.success(request, '已删除该推荐')
    return redirect('post_list')


def user_login(request):
    if not is_site_open():
        return redirect('maintenance')
    if is_beta_mode() and not has_beta_access(request):
        return redirect(f"{reverse('beta_gate')}?next={request.path}")
    if request.user.is_authenticated:
        return redirect('index')
    blocked_user = request.GET.get('appeal', '')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        existing = User.objects.filter(username=username).first()
        if existing and not existing.is_staff:
            allowed, deny_msg = can_user_login(existing)
            if not allowed:
                log_login(request, username, login_type=LoginLog.LOGIN_USER, success=False)
                messages.error(request, deny_msg)
                return render(request, 'store/login.html', {'blocked_user': existing.username})
        user = authenticate(
            request,
            username=username,
            password=request.POST.get('password'),
        )
        if user:
            if not user.is_staff:
                allowed, deny_msg = can_user_login(user)
                if not allowed:
                    log_login(request, username, user=user, login_type=LoginLog.LOGIN_USER, success=False)
                    messages.error(request, deny_msg)
                    return render(request, 'store/login.html', {'blocked_user': user.username})
            if user.is_staff:
                login_staff_with_jwt(request, user, bump_version=True)
            else:
                login_with_jwt(request, user, audience=AUD_USER, bump_version=True)
            log_login(request, username, user=user, login_type=LoginLog.LOGIN_USER, success=True)
            return redirect(request.GET.get('next', 'index'))
        log_login(request, username, login_type=LoginLog.LOGIN_USER, success=False)
        messages.error(request, '用户名或密码错误')
    return render(request, 'store/login.html', {'blocked_user': blocked_user})


def public_appeal(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        detail = request.POST.get('detail', '').strip()
        user = User.objects.filter(username=username).first()
        if not user:
            messages.error(request, '用户不存在')
            return redirect('user_login')
        if len(detail) < 10:
            messages.error(request, '申诉说明至少10字')
            return redirect(f'{reverse("user_login")}?appeal={username}')
        from django.core.cache import cache
        ip = request.META.get('REMOTE_ADDR', '')
        cache_key = f'rl:appeal:{ip}'
        if cache.get(cache_key, 0) >= 3:
            messages.error(request, '申诉过于频繁，请稍后再试')
            return redirect(f'{reverse("user_login")}?appeal={username}')
        if ContentReport.objects.filter(
            reporter=user,
            report_type=ContentReport.TYPE_APPEAL,
            status=ContentReport.STATUS_PENDING,
        ).exists():
            messages.error(request, '您已有待处理的申诉，请等待管理员审核')
            return redirect('user_login')
        ContentReport.objects.create(
            report_type=ContentReport.TYPE_APPEAL,
            reporter=user,
            reason=ContentReport.REASON_OTHER,
            detail=detail,
        )
        cache.set(cache_key, cache.get(cache_key, 0) + 1, 86400)
        log_operation(
            request, OperationLog.ACTION_APPEAL_CREATE, user=user,
            detail='通过登录页提交账号申诉',
            target_type='user', target_id=user.id,
        )
        messages.success(request, '申诉已提交，请等待管理员审核处理')
        return redirect('user_login')
    return redirect('user_login')


def user_register(request):
    if not is_site_open():
        return redirect('maintenance')
    if is_beta_mode() and not has_beta_access(request):
        return redirect(f"{reverse('beta_gate')}?next={request.path}")
    if request.user.is_authenticated:
        return redirect('index')
    beta_on = is_beta_mode()
    config = ensure_beta_code() if beta_on else None
    reg_ctx = {'require_beta_code': beta_on}

    def reg_render():
        return render(request, 'store/register.html', reg_ctx)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        if beta_on and not check_invite_code(request.POST.get('invite_code', ''), config):
            messages.error(request, '邀请码无效，请向管理员获取内测邀请码')
            return reg_render()
        if not request.POST.get('agree_disclaimer'):
            messages.error(request, '注册前请阅读并同意《免责声明与用户须知》')
            return reg_render()
        if password != password2:
            messages.error(request, '两次密码不一致')
            return reg_render()
        if User.objects.filter(username=username).exists():
            messages.error(request, '用户名已存在')
            return reg_render()
        if len(password) < 4:
            messages.error(request, '密码至少4位')
            return reg_render()
        user = User.objects.create_user(
            username=username,
            password=password,
            email=request.POST.get('email', ''),
        )
        UserProfile.objects.create(
            user=user,
            phone=request.POST.get('phone', ''),
            campus=request.POST.get('campus', ''),
        )
        login_with_jwt(request, user, audience=AUD_USER, bump_version=True)
        log_operation(
            request, OperationLog.ACTION_REGISTER, user=user,
            detail=f'新用户注册 · 邮箱 {user.email or "未填"}',
            target_type='user', target_id=user.id,
        )
        messages.success(request, '注册成功，快来发布干饭情报吧')
        response = redirect('index')
        if beta_on:
            grant_beta_access(response, config)
        return response
    return reg_render()


def user_logout(request):
    if request.user.is_authenticated:
        log_operation(request, OperationLog.ACTION_LOGOUT, user=request.user, detail='前台退出登录')
    if request.user.is_authenticated and request.user.is_staff:
        logout_with_jwt(request)
    else:
        logout_with_jwt(request, audience=AUD_USER)
    return redirect('index')


@login_required
def user_center(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    my_posts = LunchPost.objects.filter(author=request.user).annotate(
        endorse_count=Count('endorsements'),
    ).order_by('-created_at')[:10]
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            request.user.email = request.POST.get('email', '')
            request.user.save()
            profile.phone = request.POST.get('phone', '')
            profile.campus = request.POST.get('campus', '')
            avatar_file = request.FILES.get('avatar')
            if avatar_file:
                compressed = compress_avatar(avatar_file)
                if profile.avatar:
                    profile.avatar.delete(save=False)
                profile.avatar = compressed
            profile.save()
            log_operation(request, OperationLog.ACTION_PROFILE_UPDATE, user=request.user, detail='更新邮箱/校区/手机')
            messages.success(request, '个人信息更新成功')
        elif action == 'appeal':
            detail = request.POST.get('appeal_detail', '').strip()
            if len(detail) < 10:
                messages.error(request, '申诉说明至少10字')
            elif ContentReport.objects.filter(
                reporter=request.user,
                report_type=ContentReport.TYPE_APPEAL,
                status=ContentReport.STATUS_PENDING,
            ).exists():
                messages.error(request, '您已有待处理的申诉')
            else:
                ContentReport.objects.create(
                    report_type=ContentReport.TYPE_APPEAL,
                    reporter=request.user,
                    reason=ContentReport.REASON_OTHER,
                    detail=detail,
                )
                log_operation(
                    request, OperationLog.ACTION_APPEAL_CREATE, user=request.user,
                    detail='提交账号申诉',
                    target_type='user', target_id=request.user.id,
                )
                messages.success(request, '申诉已提交，请等待管理员审核')
        elif action == 'password':
            old = request.POST.get('old_password')
            new = request.POST.get('new_password')
            new2 = request.POST.get('new_password2')
            if not request.user.check_password(old):
                messages.error(request, '原密码错误')
            elif new != new2:
                messages.error(request, '两次新密码不一致')
            elif len(new) < 4:
                messages.error(request, '新密码至少4位')
            else:
                request.user.set_password(new)
                request.user.save()
                bump_auth_token_version(request.user)
                log_operation(request, OperationLog.ACTION_PASSWORD_CHANGE, user=request.user, detail='用户修改密码')
                logout_with_jwt(request, audience=AUD_USER)
                messages.success(request, '密码修改成功，请重新登录')
                return redirect('user_login')
    can_post, _ = can_user_post(request.user)
    my_appeals = ContentReport.objects.filter(
        reporter=request.user,
        report_type=ContentReport.TYPE_APPEAL,
    ).order_by('-created_at')[:5]
    favorite_count = PostFavorite.objects.filter(user=request.user).count()
    total_endorsements_received = PostEndorsement.objects.filter(post__author=request.user).count()
    return render(request, 'store/user_center.html', {
        'profile': profile,
        'my_posts': my_posts,
        'can_post': can_post,
        'my_appeals': my_appeals,
        'favorite_count': favorite_count,
        'total_endorsements_received': total_endorsements_received,
    })


def user_profile(request, user_id):
    """公开的用户资料页——查看他人发布的情报和评论动态"""
    target_user = get_object_or_404(
        User.objects.select_related('profile'),
        id=user_id,
    )
    posts = LunchPost.objects.filter(author=target_user).select_related('category').prefetch_related('photos').annotate(
        comment_count=Count('comments'),
        endorse_count=Count('endorsements'),
    ).order_by('-created_at')[:20]

    recent_comments = Comment.objects.filter(user=target_user).select_related('post').order_by('-created_at')[:10]

    post_count = LunchPost.objects.filter(author=target_user).count()
    comment_count = Comment.objects.filter(user=target_user).count()
    endorse_given = PostEndorsement.objects.filter(user=target_user).count()

    return render(request, 'store/user_profile.html', {
        'target_user': target_user,
        'profile': target_user.profile if hasattr(target_user, 'profile') else None,
        'posts': posts,
        'recent_comments': recent_comments,
        'post_count': post_count,
        'comment_count': comment_count,
        'endorse_given': endorse_given,
    })


# ==================== 管理后台 ====================

def admin_login(request):
    if is_admin_jwt_authenticated(request):
        return redirect('admin_dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        user = authenticate(
            request,
            username=username,
            password=request.POST.get('password'),
        )
        if user and user.is_staff:
            login_staff_with_jwt(request, user, bump_version=True)
            log_login(request, username, user=user, login_type=LoginLog.LOGIN_ADMIN, success=True)
            return redirect('admin_dashboard')
        log_login(request, username, login_type=LoginLog.LOGIN_ADMIN, success=False)
        messages.error(request, '账号或密码错误，或您没有管理员权限')
    return render(request, 'admin/login.html')


def admin_logout(request):
    if request.user.is_authenticated:
        log_operation(request, OperationLog.ACTION_ADMIN_LOGOUT, user=request.user, detail='管理后台退出登录')
    logout_with_jwt(request)
    return redirect('admin_login')


def jwt_refresh_user(request):
    if request.method != 'POST':
        return redirect('index')
    refresh = get_refresh_token(request, audience=AUD_USER)
    if not refresh:
        logout_with_jwt(request, audience=AUD_USER)
        return redirect('user_login')
    try:
        user = verify_refresh_token(refresh, audience=AUD_USER)
    except JwtAuthError:
        logout_with_jwt(request, audience=AUD_USER)
        messages.error(request, '登录已失效，请重新登录')
        return redirect('user_login')
    request._jwt_pending_auth = {
        'tokens': issue_token_pair(user, audience=AUD_USER),
        'audience': AUD_USER,
    }
    request.user = user
    next_url = request.POST.get('next') or request.GET.get('next') or 'index'
    return redirect(next_url)


def jwt_refresh_admin(request):
    if request.method != 'POST':
        return redirect('admin_dashboard')
    refresh = get_refresh_token(request, audience=AUD_ADMIN)
    if not refresh:
        logout_with_jwt(request, audience=AUD_ADMIN)
        return redirect('admin_login')
    try:
        user = verify_refresh_token(refresh, audience=AUD_ADMIN)
    except JwtAuthError:
        logout_with_jwt(request, audience=AUD_ADMIN)
        messages.error(request, '管理员登录已失效，请重新登录')
        return redirect('admin_login')
    request._jwt_pending_auth = {
        'tokens': issue_token_pair(user, audience=AUD_ADMIN),
        'audience': AUD_ADMIN,
    }
    request.user = user
    next_url = request.POST.get('next') or request.GET.get('next') or 'admin_dashboard'
    return redirect(next_url)


@user_passes_test(is_admin, login_url='admin_login')
def admin_dashboard(request):
    config = SiteConfig.get_singleton()
    if request.method == 'POST':
        action = request.POST.get('action', '')
        site_actions = {
            'toggle_site', 'update_closed_message', 'toggle_beta',
            'update_beta_code', 'regenerate_beta_code',
        }
        if action in site_actions and not is_super_admin(request.user):
            messages.error(request, '仅超级管理员可修改网站开关与内测设置')
            return redirect('admin_dashboard')
    if request.method == 'POST' and request.POST.get('action') == 'toggle_site':
        config.is_site_open = not config.is_site_open
        config.updated_by = request.user
        config.save()
        if config.is_site_open:
            log_operation(
                request, OperationLog.ACTION_ADMIN_SITE_OPEN, user=request.user,
                detail='管理员开放网站',
            )
            messages.success(request, '网站已重新开放，用户可正常访问')
        else:
            log_operation(
                request, OperationLog.ACTION_ADMIN_SITE_CLOSE, user=request.user,
                detail='管理员关闭网站',
            )
            messages.success(request, '网站已关闭，仅管理员可登录后台')
        return redirect('admin_dashboard')
    if request.method == 'POST' and request.POST.get('action') == 'update_closed_message':
        config.closed_message_zh = request.POST.get('closed_message_zh', '').strip()
        config.updated_by = request.user
        config.save()
        messages.success(request, '关站说明已更新')
        return redirect('admin_dashboard')
    if request.method == 'POST' and request.POST.get('action') == 'toggle_beta':
        if not config.is_beta_mode:
            config.is_beta_mode = True
            ensure_beta_code(config)
            log_operation(request, OperationLog.ACTION_ADMIN_BETA_ON, user=request.user, detail='开启内测模式')
            messages.success(request, '内测模式已开启，用户需输入邀请码方可访问')
        else:
            config.is_beta_mode = False
            log_operation(request, OperationLog.ACTION_ADMIN_BETA_OFF, user=request.user, detail='关闭内测模式')
            messages.success(request, '内测模式已关闭，所有用户可正常访问')
        config.updated_by = request.user
        config.save()
        return redirect('admin_dashboard')
    if request.method == 'POST' and request.POST.get('action') == 'update_beta_code':
        new_code = request.POST.get('beta_invite_code', '').strip().upper()
        if len(new_code) < 4:
            messages.error(request, '邀请码至少 4 位')
        else:
            config.beta_invite_code = new_code
            config.beta_code_revision += 1
            config.updated_by = request.user
            config.save()
            log_operation(
                request, OperationLog.ACTION_ADMIN_BETA_CODE, user=request.user,
                detail=f'更新内测邀请码为 {new_code}',
            )
            messages.success(request, '邀请码已更新，旧邀请码将失效')
        return redirect('admin_dashboard')
    if request.method == 'POST' and request.POST.get('action') == 'regenerate_beta_code':
        config.beta_invite_code = generate_invite_code()
        config.beta_code_revision += 1
        config.updated_by = request.user
        config.save()
        log_operation(
            request, OperationLog.ACTION_ADMIN_BETA_CODE, user=request.user,
            detail=f'重新生成内测邀请码 {config.beta_invite_code}',
        )
        messages.success(request, f'已生成新邀请码：{config.beta_invite_code}')
        return redirect('admin_dashboard')
    stats = get_dashboard_stats()
    return render(request, 'admin/dashboard.html', {
        'total_users': User.objects.filter(is_staff=False).count(),
        'total_posts': LunchPost.objects.count(),
        'total_comments': Comment.objects.count(),
        'total_categories': FoodCategory.objects.count(),
        'total_announcements': Announcement.objects.filter(is_active=True).count(),
        'recent_posts': LunchPost.objects.select_related('author').order_by('-created_at')[:8],
        'recent_announcements': Announcement.objects.select_related('author').order_by('-created_at')[:5],
        'site_config': config,
        'stats': stats,
        'is_super_admin': is_super_admin(request.user),
        'section': 'dashboard',
    })


@user_passes_test(is_admin, login_url='admin_login')
def admin_user_list(request):
    users = list(User.objects.filter(is_staff=False).order_by('-date_joined'))
    existing = set(
        UserProfile.objects.filter(user__in=users).values_list('user_id', flat=True)
    )
    for u in users:
        if u.id not in existing:
            UserProfile.objects.create(user=u)
    users = User.objects.filter(is_staff=False).select_related('profile').order_by('-date_joined')
    return render(request, 'admin/user_list.html', {
        'users': users,
        'section': 'users',
    })


@user_passes_test(is_admin, login_url='admin_login')
def admin_user_punish(request, user_id):
    if request.method != 'POST':
        return redirect('admin_user_list')
    target = get_object_or_404(User, id=user_id)
    if target.is_staff:
        messages.error(request, '不能处罚管理员账号')
        return redirect('admin_user_list')

    action = request.POST.get('action', '')
    note = request.POST.get('note', '').strip()[:500]
    profile, _ = UserProfile.objects.get_or_create(user=target)
    profile.moderation_note = note
    profile.moderated_by = request.user
    profile.moderated_at = timezone.now()

    action_map = {
        'ban': (
            OperationLog.ACTION_ADMIN_USER_BAN,
            lambda: _apply_ban(profile, target, True),
            f'封号用户 {target.username}',
        ),
        'unban': (
            OperationLog.ACTION_ADMIN_USER_UNBAN,
            lambda: _apply_ban(profile, target, False),
            f'解除封号 {target.username}',
        ),
        'mute': (
            OperationLog.ACTION_ADMIN_USER_MUTE,
            lambda: _apply_flag(profile, 'is_muted', True),
            f'禁言用户 {target.username}',
        ),
        'unmute': (
            OperationLog.ACTION_ADMIN_USER_UNMUTE,
            lambda: _apply_flag(profile, 'is_muted', False),
            f'解除禁言 {target.username}',
        ),
        'restrict_login': (
            OperationLog.ACTION_ADMIN_USER_RESTRICT_LOGIN,
            lambda: _apply_flag(profile, 'login_restricted', True),
            f'限制登录 {target.username}',
        ),
        'allow_login': (
            OperationLog.ACTION_ADMIN_USER_ALLOW_LOGIN,
            lambda: _apply_flag(profile, 'login_restricted', False),
            f'解除登录限制 {target.username}',
        ),
    }

    if action not in action_map:
        messages.error(request, '无效操作')
        return redirect('admin_user_list')

    log_action, apply_fn, detail = action_map[action]
    apply_fn()
    profile.refresh_from_db()
    log_operation(
        request, log_action, user=request.user,
        detail=f'{detail}' + (f' · {note}' if note else ''),
        target_type='user', target_id=target.id,
    )
    messages.success(request, '处罚状态已更新')
    referer = request.META.get('HTTP_REFERER', '')
    referer_path = urlparse(referer).path
    if '/admin-panel/reports/' in referer_path:
        return redirect(referer_path)
    return redirect('admin_user_list')


def _apply_ban(profile, user, banned):
    profile.is_banned = banned
    user.is_active = not banned
    profile.save()
    user.save(update_fields=['is_active'])
    bump_auth_token_version(user)


def _apply_flag(profile, field, value):
    setattr(profile, field, value)
    profile.save(update_fields=[field, 'moderation_note', 'moderated_by', 'moderated_at'])
    if field == 'login_restricted' and value:
        bump_auth_token_version(profile.user)


@user_passes_test(is_admin, login_url='admin_login')
def admin_user_reset_password(request, user_id):
    if request.method != 'POST':
        return redirect('admin_user_list')
    target = get_object_or_404(User, id=user_id)
    if target.is_staff:
        messages.error(request, '不能重置管理员密码')
        return redirect('admin_user_list')
    new_password = request.POST.get('new_password', '').strip()
    confirm = request.POST.get('new_password2', '').strip()
    if len(new_password) < 4:
        messages.error(request, '新密码至少4位')
        return redirect('admin_user_list')
    if new_password != confirm:
        messages.error(request, '两次密码不一致')
        return redirect('admin_user_list')
    target.set_password(new_password)
    target.save(update_fields=['password'])
    bump_auth_token_version(target)
    log_operation(
        request, OperationLog.ACTION_ADMIN_USER_RESET_PASSWORD, user=request.user,
        detail=f'重置用户 {target.username} 的登录密码',
        target_type='user', target_id=target.id,
    )
    messages.success(request, f'已重置用户 {target.username} 的密码，请告知用户新密码')
    return redirect('admin_user_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_user_update_profile(request, user_id):
    if request.method != 'POST':
        return redirect('admin_user_list')
    target = get_object_or_404(User, id=user_id)
    if target.is_staff:
        messages.error(request, '不能修改管理员资料')
        return redirect('admin_user_list')
    profile, _ = UserProfile.objects.get_or_create(user=target)
    target.email = request.POST.get('email', '').strip()
    profile.phone = request.POST.get('phone', '').strip()[:20]
    profile.campus = request.POST.get('campus', '').strip()[:100]
    target.save(update_fields=['email'])
    profile.save(update_fields=['phone', 'campus'])
    log_operation(
        request, OperationLog.ACTION_ADMIN_USER_PROFILE_UPDATE, user=request.user,
        detail=f'更新用户 {target.username} 的资料',
        target_type='user', target_id=target.id,
    )
    messages.success(request, f'已更新用户 {target.username} 的资料')
    return redirect('admin_user_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_user_delete(request, user_id):
    if request.method != 'POST':
        return redirect('admin_user_list')
    user = get_object_or_404(User, id=user_id)
    if user.is_staff:
        messages.error(request, '不能删除管理员账号')
    else:
        log_operation(
            request, OperationLog.ACTION_ADMIN_USER_DELETE, user=request.user,
            detail=f'删除用户 {user.username}',
            target_type='user', target_id=user.id,
        )
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM store_betaaccount WHERE user_id = %s', [user.id])
            cursor.execute('DELETE FROM store_betaaccount WHERE created_by_id = %s', [user.id])
        user.delete()
        messages.success(request, '用户已删除')
    return redirect('admin_user_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_post_list(request):
    return render(request, 'admin/post_list.html', {
        'posts': LunchPost.objects.select_related('category', 'author').annotate(
            comment_count=Count('comments'),
            endorse_count=Count('endorsements'),
        ).order_by('-created_at'),
        'section': 'posts',
    })


@user_passes_test(is_admin, login_url='admin_login')
def admin_post_delete(request, post_id):
    post = get_object_or_404(LunchPost, id=post_id)
    log_operation(
        request, OperationLog.ACTION_ADMIN_POST_DELETE, user=request.user,
        detail=f'管理员删除《{post.title}》',
        target_type='post', target_id=post.id,
    )
    post.delete()
    messages.success(request, '推荐已删除')
    return redirect('admin_post_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_comment_delete(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    log_operation(
        request, OperationLog.ACTION_ADMIN_COMMENT_DELETE, user=request.user,
        detail=f'删除 {comment.user.username} 在《{comment.post.title}》的评论',
        target_type='comment', target_id=comment.id,
    )
    comment.delete()
    messages.success(request, '评论已删除')
    return redirect('admin_post_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_category_list(request):
    return render(request, 'admin/category_list.html', {
        'categories': FoodCategory.objects.annotate(post_count=Count('posts')),
        'section': 'categories',
    })


@user_passes_test(is_admin, login_url='admin_login')
def admin_category_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = FoodCategory.objects.create(
            name=name,
            icon=request.POST.get('icon', '🍱'),
            sort_order=request.POST.get('sort_order', 0) or 0,
        )
        log_operation(
            request, OperationLog.ACTION_ADMIN_CATEGORY_ADD, user=request.user,
            detail=f'添加分类 {name}',
            target_type='category', target_id=category.id,
        )
        messages.success(request, '分类添加成功')
    return redirect('admin_category_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_category_edit(request, category_id):
    category = get_object_or_404(FoodCategory, id=category_id)
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.icon = request.POST.get('icon', '🍱')
        category.sort_order = request.POST.get('sort_order', 0) or 0
        category.save()
        log_operation(
            request, OperationLog.ACTION_ADMIN_CATEGORY_EDIT, user=request.user,
            detail=f'编辑分类 {category.name}',
            target_type='category', target_id=category.id,
        )
        messages.success(request, '分类已更新')
    return redirect('admin_category_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_category_delete(request, category_id):
    category = get_object_or_404(FoodCategory, id=category_id)
    log_operation(
        request, OperationLog.ACTION_ADMIN_CATEGORY_DELETE, user=request.user,
        detail=f'删除分类 {category.name}',
        target_type='category', target_id=category.id,
    )
    category.delete()
    messages.success(request, '分类已删除')
    return redirect('admin_category_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_announcement_list(request):
    return render(request, 'admin/announcement_list.html', {
        'announcements': Announcement.objects.select_related('author').order_by('-is_pinned', '-created_at'),
        'section': 'announcements',
    })


@user_passes_test(is_admin, login_url='admin_login')
def admin_announcement_add(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if not title or not content:
            messages.error(request, '标题和内容为必填项')
            return redirect('admin_announcement_list')
        announcement = Announcement.objects.create(
            title=title,
            content=content,
            is_active=request.POST.get('is_active') == '1',
            is_pinned=request.POST.get('is_pinned') == '1',
            author=request.user,
        )
        log_operation(
            request, OperationLog.ACTION_ADMIN_ANNOUNCEMENT_ADD, user=request.user,
            detail=f'发布公告《{announcement.title}》',
            target_type='announcement', target_id=announcement.id,
        )
        messages.success(request, '公告发布成功')
    return redirect('admin_announcement_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_announcement_edit(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if not title or not content:
            messages.error(request, '标题和内容为必填项')
            return redirect('admin_announcement_list')
        announcement.title = title
        announcement.content = content
        announcement.is_active = request.POST.get('is_active') == '1'
        announcement.is_pinned = request.POST.get('is_pinned') == '1'
        announcement.save()
        log_operation(
            request, OperationLog.ACTION_ADMIN_ANNOUNCEMENT_EDIT, user=request.user,
            detail=f'编辑公告《{announcement.title}》',
            target_type='announcement', target_id=announcement.id,
        )
        messages.success(request, '公告已更新')
    return redirect('admin_announcement_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_announcement_delete(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    log_operation(
        request, OperationLog.ACTION_ADMIN_ANNOUNCEMENT_DELETE, user=request.user,
        detail=f'删除公告《{announcement.title}》',
        target_type='announcement', target_id=announcement.id,
    )
    announcement.delete()
    messages.success(request, '公告已删除')
    return redirect('admin_announcement_list')


@user_passes_test(is_admin, login_url='admin_login')
def admin_profile(request):
    if request.method == 'POST':
        new_password = request.POST.get('password')
        if new_password:
            request.user.set_password(new_password)
            request.user.save()
            log_operation(
                request, OperationLog.ACTION_ADMIN_PASSWORD_CHANGE, user=request.user,
                detail='管理员修改密码',
            )
            messages.success(request, '密码修改成功，请重新登录')
            return redirect('admin_login')
        messages.error(request, '请输入新密码')
    return render(request, 'admin/profile.html', {'section': 'profile'})


@user_passes_test(is_admin, login_url='admin_login')
def admin_log_list(request):
    tab = request.GET.get('tab', 'login')
    keyword = request.GET.get('q', '').strip()
    if tab == 'operation':
        logs = OperationLog.objects.select_related('user').order_by('-created_at')
        if keyword:
            logs = logs.filter(
                Q(username__icontains=keyword)
                | Q(detail__icontains=keyword)
                | Q(ip_address__icontains=keyword)
                | Q(action__icontains=keyword),
            )
    else:
        tab = 'login'
        logs = LoginLog.objects.select_related('user').order_by('-created_at')
        if keyword:
            logs = logs.filter(
                Q(username__icontains=keyword)
                | Q(ip_address__icontains=keyword)
                | Q(user_agent__icontains=keyword),
            )
    return render(request, 'admin/log_list.html', {
        'tab': tab,
        'keyword': keyword,
        'logs': logs[:500],
        'section': 'logs',
    })


@user_passes_test(is_admin, login_url='admin_login')
def admin_log_delete(request, log_id):
    if request.method != 'POST':
        return redirect('admin_log_list')
    tab = request.GET.get('tab', 'login')
    if tab == 'operation':
        log_entry = get_object_or_404(OperationLog, id=log_id)
        detail = f'删除操作日志 #{log_entry.id} · {log_entry.get_action_display()} · {log_entry.username}'
        log_entry.delete()
    else:
        log_entry = get_object_or_404(LoginLog, id=log_id)
        detail = f'删除登录日志 #{log_entry.id} · {log_entry.username}'
        log_entry.delete()
    log_operation(
        request, OperationLog.ACTION_ADMIN_LOG_DELETE, user=request.user,
        detail=detail,
        target_type='log', target_id=log_id,
    )
    messages.success(request, '日志已删除')
    return redirect(f'{reverse("admin_log_list")}?tab={tab}')

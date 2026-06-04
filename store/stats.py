from datetime import datetime, timedelta, time

from django.db.models import Count, Q
from django.utils import timezone

from django.contrib.auth.models import User

from .models import LunchPost, Comment, ContentReport, FoodCategory, OperationLog, PostEndorsement


def _local_day_bounds(day):
    """MySQL + USE_TZ 下 created_at__date 不可靠，改用本地时区时间范围。"""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    return start, start + timedelta(days=1)


def _count_on_local_day(queryset, day, field='created_at'):
    start, end = _local_day_bounds(day)
    return queryset.filter(**{f'{field}__gte': start, f'{field}__lt': end}).count()


def get_dashboard_stats():
    since = timezone.now() - timedelta(days=7)
    posts_7d = LunchPost.objects.filter(created_at__gte=since).count()
    comments_7d = Comment.objects.filter(created_at__gte=since).count()
    active_posters = User.objects.filter(lunch_posts__created_at__gte=since).distinct().count()
    active_commenters = User.objects.filter(lunch_comments__created_at__gte=since).distinct().count()
    active_users = User.objects.filter(
        Q(lunch_posts__created_at__gte=since) | Q(lunch_comments__created_at__gte=since),
    ).distinct().count()
    pending_reports = ContentReport.objects.filter(status=ContentReport.STATUS_PENDING).count()
    top_categories = (
        FoodCategory.objects.annotate(post_count=Count('posts'))
        .filter(post_count__gt=0)
        .order_by('-post_count')[:5]
    )
    top_locations = (
        LunchPost.objects.values('location')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:5]
    )
    daily_posts = []
    for i in range(6, -1, -1):
        day = timezone.localdate() - timedelta(days=i)
        daily_posts.append({
            'label': day.strftime('%m-%d'),
            'count': _count_on_local_day(LunchPost.objects.all(), day),
        })
    max_daily = max((item['count'] for item in daily_posts), default=1) or 1
    return {
        'posts_7d': posts_7d,
        'comments_7d': comments_7d,
        'active_users_7d': active_users,
        'active_posters_7d': active_posters,
        'active_commenters_7d': active_commenters,
        'pending_reports': pending_reports,
        'top_categories': top_categories,
        'top_locations': top_locations,
        'daily_posts': daily_posts,
        'daily_posts_max': max_daily,
    }


def get_home_chart_data():
    """首页 ECharts：近 7 日新增菜品折线 + 分类菜品占比饼图。"""
    category_chart = [
        {
            'name': f'{c.icon} {c.name}'.strip(),
            'value': c.post_count,
        }
        for c in FoodCategory.objects.annotate(post_count=Count('posts'))
        .filter(post_count__gt=0)
        .order_by('-post_count')
    ]
    uncategorized = LunchPost.objects.filter(category__isnull=True).count()
    if uncategorized:
        category_chart.append({'name': '🍽 未分类', 'value': uncategorized})
    daily_new_posts = []
    for i in range(6, -1, -1):
        day = timezone.localdate() - timedelta(days=i)
        daily_new_posts.append({
            'label': day.strftime('%m-%d'),
            'count': _count_on_local_day(LunchPost.objects.all(), day),
        })
    return {
        'categories': category_chart,
        'daily_new_posts': daily_new_posts,
        'total_endorsements': PostEndorsement.objects.count(),
        'total_posts': LunchPost.objects.count(),
    }

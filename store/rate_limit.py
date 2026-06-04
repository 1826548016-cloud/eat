from django.core.cache import cache

LIMITS = {
    'post_create': (5, 3600),
    'post_edit': (10, 3600),
    'comment': (30, 3600),
    'report': (10, 86400),
}


def check_rate_limit(user, action):
    if not user or not user.is_authenticated or user.is_staff:
        return True, ''
    limit, window = LIMITS[action]
    key = f'rl:{action}:{user.id}'
    count = cache.get(key, 0)
    if count >= limit:
        return False, '操作过于频繁，请稍后再试'
    return True, ''


def hit_rate_limit(user, action):
    if not user or not user.is_authenticated or user.is_staff:
        return
    _, window = LIMITS[action]
    key = f'rl:{action}:{user.id}'
    count = cache.get(key, 0)
    cache.set(key, count + 1, window)

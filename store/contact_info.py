"""站点管理员联系方式（存于 SiteConfig 单例）。"""

from .models import SiteConfig

CONTACT_LABELS = {
    'email': '邮箱',
    'phone': '电话',
    'wechat': '微信',
    'qq': 'QQ',
    'telegram': 'Telegram',
    'weibo': '微博',
    'xiaohongshu': '小红书',
    'github': 'GitHub',
    'bilibili': '哔哩哔哩',
}


def contact_intro(config):
    return config.contact_intro_zh or config.contact_intro_en


def has_contact_info(config):
    return bool(get_contact_channels(config))


def get_contact_channels(config):
    """返回前台可展示的联系方式列表。"""
    channels = []
    if config.contact_email:
        channels.append({
            'key': 'email',
            'icon': '✉️',
            'label': CONTACT_LABELS['email'],
            'value': config.contact_email,
            'href': f'mailto:{config.contact_email}',
            'external': False,
        })
    if config.contact_phone:
        channels.append({
            'key': 'phone',
            'icon': '📞',
            'label': CONTACT_LABELS['phone'],
            'value': config.contact_phone,
            'href': f'tel:{config.contact_phone.replace(" ", "")}',
            'external': False,
        })
    if config.contact_wechat:
        channels.append({
            'key': 'wechat',
            'icon': '💬',
            'label': CONTACT_LABELS['wechat'],
            'value': config.contact_wechat,
            'href': '',
            'external': False,
        })
    if config.contact_qq:
        qq = config.contact_qq.strip()
        href = f'https://wpa.qq.com/msgrd?v=3&uin={qq}&site=qq&menu=yes' if qq.isdigit() else ''
        channels.append({
            'key': 'qq',
            'icon': '🐧',
            'label': CONTACT_LABELS['qq'],
            'value': config.contact_qq,
            'href': href,
            'external': bool(href),
        })
    if config.contact_telegram:
        tg = config.contact_telegram.strip().lstrip('@')
        href = config.contact_telegram if config.contact_telegram.startswith('http') else f'https://t.me/{tg}'
        channels.append({
            'key': 'telegram',
            'icon': '✈️',
            'label': CONTACT_LABELS['telegram'],
            'value': config.contact_telegram,
            'href': href,
            'external': True,
        })
    url_fields = (
        ('weibo', config.contact_weibo, 'weibo', '🔗'),
        ('xiaohongshu', config.contact_xiaohongshu, 'xiaohongshu', '📕'),
        ('github', config.contact_github, 'github', '💻'),
        ('bilibili', config.contact_bilibili, 'bilibili', '📺'),
    )
    for key, url, label_key, icon in url_fields:
        if url:
            channels.append({
                'key': key,
                'icon': icon,
                'label': CONTACT_LABELS[label_key],
                'value': url,
                'href': url,
                'external': True,
            })
    return channels

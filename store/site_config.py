from .models import SiteConfig


def get_site_config():
    return SiteConfig.get_singleton()


def is_site_open():
    return get_site_config().is_site_open


def closed_message():
    config = get_site_config()
    return config.closed_message_zh or config.closed_message_en


def get_contact_context():
    from .contact_info import contact_intro, get_contact_channels, has_contact_info

    config = get_site_config()
    return {
        'contact_intro': contact_intro(config),
        'contact_channels': get_contact_channels(config),
        'has_contact_info': has_contact_info(config),
    }

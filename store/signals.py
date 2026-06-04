import os

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import LunchPost, PostImage, UserProfile


def _delete_file(file_field):
    """删除文件字段对应的实际文件（如果存在）。"""
    if not file_field:
        return
    path = file_field.path
    if os.path.isfile(path):
        os.remove(path)


@receiver(post_delete, sender=PostImage)
def auto_delete_post_image(sender, instance, **kwargs):
    """删除 PostImage 记录时同时删除对应的图片文件。"""
    _delete_file(instance.image)


@receiver(post_delete, sender=LunchPost)
def auto_delete_lunch_post_files(sender, instance, **kwargs):
    """删除 LunchPost 记录时同时删除封面图和门头照片。"""
    _delete_file(instance.image)
    _delete_file(instance.storefront_image)


@receiver(post_delete, sender=UserProfile)
def auto_delete_user_avatar(sender, instance, **kwargs):
    """删除 UserProfile 记录时同时删除头像文件。"""
    _delete_file(instance.avatar)

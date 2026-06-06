"""Backfill thumbnails for existing PostImage records that lack them."""
from django.core.management.base import BaseCommand

from store.models import PostImage
from store.post_media import make_thumbnail


class Command(BaseCommand):
    help = '为已有图片生成缩略图（若尚未生成）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制重新生成所有缩略图（即使已存在）',
        )

    def handle(self, *args, **options):
        force = options['force']
        photos = PostImage.objects.select_related('post')
        created = 0
        skipped = 0

        for photo in photos:
            if not force and photo.thumbnail:
                skipped += 1
                continue

            if not photo.image:
                skipped += 1
                continue

            try:
                # Open the original image file and generate thumbnail
                photo.image.open('rb')
                thumb = make_thumbnail(photo.image.file)
                photo.thumbnail = thumb
                photo.save(update_fields=['thumbnail'])
                created += 1
                self.stdout.write(f'  OK  {photo}')
            except Exception as e:
                self.stderr.write(f'  FAIL {photo}: {e}')
            finally:
                photo.image.close()

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {created} thumbnails generated, {skipped} skipped.'
        ))

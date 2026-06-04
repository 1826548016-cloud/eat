import io
from pathlib import Path

from django.core.files.uploadedfile import InMemoryUploadedFile

MAX_FOOD_PHOTOS = 9
MAX_IMAGE_DIMENSION = 1920
JPEG_QUALITY = 85


def compress_image(uploaded_file, max_dim=MAX_IMAGE_DIMENSION, quality=JPEG_QUALITY):
    """将上传的图片压缩后返回 InMemoryUploadedFile，支持 JPEG / PNG / WebP。"""
    from PIL import Image as PilImage

    img = PilImage.open(uploaded_file)
    img_format = img.format or 'JPEG'
    if img_format.upper() not in ('JPEG', 'PNG', 'WEBP'):
        img_format = 'JPEG'

    original_mode = img.mode
    if img_format.upper() == 'JPEG' and original_mode in ('RGBA', 'P', 'LA'):
        background = PilImage.new('RGB', img.size, (255, 255, 255))
        if original_mode == 'P':
            img = img.convert('RGBA')
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img)
        img = background

    if max(img.width, img.height) > max_dim:
        ratio = max_dim / max(img.width, img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, PilImage.LANCZOS)

    buf = io.BytesIO()
    save_kwargs = {'optimize': True}
    if img_format.upper() == 'JPEG':
        save_kwargs['quality'] = quality
        if img.mode != 'RGB':
            img = img.convert('RGB')
    elif img_format.upper() == 'WEBP':
        save_kwargs['quality'] = quality
    elif img_format.upper() == 'PNG':
        save_kwargs['compress_level'] = 6

    img.save(buf, format=img_format, **save_kwargs)
    buf.seek(0)

    original_name = getattr(uploaded_file, 'name', 'image.jpg')
    stem = Path(original_name).stem
    ext_map = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}
    new_name = f'{stem}{ext_map.get(img_format.upper(), ".jpg")}'

    return InMemoryUploadedFile(
        buf,
        field_name=None,
        name=new_name,
        content_type=f'image/{img_format.lower()}',
        size=buf.getbuffer().nbytes,
        charset=None,
    )


def save_post_uploads(post, *, food_files=None, storefront_file=None):
    from .models import PostImage

    if storefront_file:
        compressed = compress_image(storefront_file)
        post.storefront_image = compressed
        post.save(update_fields=['storefront_image'])

    files = [f for f in (food_files or []) if f]
    if not files:
        return

    existing = post.photos.count()
    if existing + len(files) > MAX_FOOD_PHOTOS:
        files = files[: max(0, MAX_FOOD_PHOTOS - existing)]

    for index, uploaded in enumerate(files):
        compressed = compress_image(uploaded)
        PostImage.objects.create(post=post, image=compressed, sort_order=existing + index)

    post.sync_cover_image()

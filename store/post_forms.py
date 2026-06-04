"""推荐表单共用逻辑。"""

from .post_media import MAX_FOOD_PHOTOS, save_post_uploads


def validate_post_form(request):
    title = request.POST.get('title', '').strip()
    location = request.POST.get('location', '').strip()
    description = request.POST.get('description', '').strip()
    if not title or not location or not description:
        return None, '店名、详细地址和推荐理由为必填项'
    food_files = request.FILES.getlist('photos')
    if len(food_files) > MAX_FOOD_PHOTOS:
        return None, f'实拍图最多上传 {MAX_FOOD_PHOTOS} 张'
    return {
        'title': title,
        'location': location,
        'description': description,
        'price': request.POST.get('price', '').strip(),
        'category_id': request.POST.get('category') or None,
        'food_files': food_files,
        'storefront_file': request.FILES.get('storefront_image'),
        'remove_photo_ids': request.POST.getlist('remove_photos'),
    }, None


def apply_post_form(post, data, *, is_new=False):
    post.title = data['title']
    post.location = data['location']
    post.description = data['description']
    post.price = data['price']
    post.category_id = data['category_id']
    if not is_new:
        post.is_edited = True
    post.save()

    if data['remove_photo_ids']:
        from .models import PostImage
        remove_ids = [int(x) for x in data['remove_photo_ids'] if str(x).isdigit()]
        if remove_ids:
            post.photos.filter(id__in=remove_ids).delete()

    save_post_uploads(
        post,
        food_files=data['food_files'],
        storefront_file=data['storefront_file'],
    )
    post.sync_cover_image()

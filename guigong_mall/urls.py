from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as _media_serve
import os


def cached_media_serve(request, path, document_root=None, **kwargs):
    """Serve media files with browser cache headers (works without nginx)."""
    response = _media_serve(request, path, document_root=document_root, **kwargs)
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.ico'):
        response['Cache-Control'] = 'public, max-age=2592000, immutable'
    else:
        response['Cache-Control'] = 'public, max-age=3600'
    return response


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(
            r'^media/(?P<path>.*)$',
            cached_media_serve,
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]

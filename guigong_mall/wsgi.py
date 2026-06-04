import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'guigong_mall.settings')
application = get_wsgi_application()

from django.db import migrations


def promote_primary_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='admin', is_staff=True).update(is_superuser=True)


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0014_post_images'),
    ]

    operations = [
        migrations.RunPython(promote_primary_admin, migrations.RunPython.noop),
    ]

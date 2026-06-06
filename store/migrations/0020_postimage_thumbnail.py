from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0018_post_endorsement'),
    ]

    operations = [
        migrations.AddField(
            model_name='postimage',
            name='thumbnail',
            field=models.ImageField(blank=True, upload_to='lunch/thumbs/', verbose_name='缩略图'),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0012_friend_links'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='auth_token_version',
            field=models.PositiveIntegerField(default=0, verbose_name='认证令牌版本'),
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('store', '0017_alter_operationlog_action'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostEndorsement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='推荐时间')),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='endorsements', to='store.lunchpost', verbose_name='情报')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='post_endorsements', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '用户推荐',
                'verbose_name_plural': '用户推荐',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='postendorsement',
            constraint=models.UniqueConstraint(fields=('user', 'post'), name='unique_post_endorsement'),
        ),
    ]

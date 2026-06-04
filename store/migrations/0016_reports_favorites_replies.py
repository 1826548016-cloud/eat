from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0015_promote_superuser'),
    ]

    operations = [
        migrations.AddField(
            model_name='lunchpost',
            name='is_edited',
            field=models.BooleanField(default=False, verbose_name='已编辑'),
        ),
        migrations.AddField(
            model_name='comment',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='replies',
                to='store.comment',
                verbose_name='回复的评论',
            ),
        ),
        migrations.CreateModel(
            name='PostFavorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='收藏时间')),
                ('post', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='favorited_by',
                    to='store.lunchpost',
                    verbose_name='推荐',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='post_favorites',
                    to='auth.user',
                    verbose_name='用户',
                )),
            ],
            options={
                'verbose_name': '收藏',
                'verbose_name_plural': '收藏',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='postfavorite',
            constraint=models.UniqueConstraint(fields=('user', 'post'), name='unique_post_favorite'),
        ),
        migrations.CreateModel(
            name='ContentReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_type', models.CharField(
                    choices=[('post', '举报推荐'), ('comment', '举报评论'), ('appeal', '账号申诉')],
                    max_length=10,
                    verbose_name='类型',
                )),
                ('reason', models.CharField(
                    choices=[
                        ('spam', '广告/刷屏'),
                        ('abuse', '辱骂/引战'),
                        ('false_info', '虚假信息'),
                        ('privacy', '侵犯隐私'),
                        ('other', '其他'),
                    ],
                    max_length=20,
                    verbose_name='原因',
                )),
                ('detail', models.TextField(blank=True, max_length=1000, verbose_name='补充说明')),
                ('status', models.CharField(
                    choices=[('pending', '待处理'), ('resolved', '已处理'), ('dismissed', '已驳回')],
                    default='pending',
                    max_length=10,
                    verbose_name='状态',
                )),
                ('admin_note', models.CharField(blank=True, max_length=500, verbose_name='处理备注')),
                ('handled_at', models.DateTimeField(blank=True, null=True, verbose_name='处理时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='提交时间')),
                ('comment', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reports',
                    to='store.comment',
                    verbose_name='相关评论',
                )),
                ('handled_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='handled_reports',
                    to='auth.user',
                    verbose_name='处理人',
                )),
                ('post', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reports',
                    to='store.lunchpost',
                    verbose_name='相关推荐',
                )),
                ('reporter', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='content_reports',
                    to='auth.user',
                    verbose_name='提交人',
                )),
            ],
            options={
                'verbose_name': '举报/申诉',
                'verbose_name_plural': '举报/申诉',
                'ordering': ['-created_at'],
            },
        ),
    ]

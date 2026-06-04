from django.db import migrations, models


def migrate_legacy_images(apps, schema_editor):
    LunchPost = apps.get_model('store', 'LunchPost')
    PostImage = apps.get_model('store', 'PostImage')
    for post in LunchPost.objects.exclude(image='').exclude(image__isnull=True):
        if post.image and not PostImage.objects.filter(post=post).exists():
            PostImage.objects.create(post=post, image=post.image, sort_order=0)


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0013_auth_token_version'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lunchpost',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='lunch/', verbose_name='封面图'),
        ),
        migrations.AlterField(
            model_name='lunchpost',
            name='location',
            field=models.CharField(
                help_text='如：XX大学北门美食街3号铺、一食堂二楼东侧',
                max_length=300,
                verbose_name='详细地址',
            ),
        ),
        migrations.AddField(
            model_name='lunchpost',
            name='storefront_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='lunch/storefront/',
                verbose_name='商家门头照片',
            ),
        ),
        migrations.CreateModel(
            name='PostImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='lunch/photos/', verbose_name='实拍图')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='上传时间')),
                ('post', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='photos',
                    to='store.lunchpost',
                    verbose_name='推荐',
                )),
            ],
            options={
                'verbose_name': '推荐图片',
                'verbose_name_plural': '推荐图片',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.RunPython(migrate_legacy_images, migrations.RunPython.noop),
    ]

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from store.models import FoodCategory, LunchPost, UserProfile


class Command(BaseCommand):
    help = '初始化干饭情报局分类与示例情报'

    def handle(self, *args, **options):
        categories = [
            ('食堂', '🏫', 1),
            ('外卖', '🛵', 2),
            ('小吃街', '🍢', 3),
            ('便利店', '🏪', 4),
            ('轻食', '🥗', 5),
        ]
        cat_map = {}
        for name, icon, order in categories:
            cat, _ = FoodCategory.objects.get_or_create(
                name=name, defaults={'icon': icon, 'sort_order': order},
            )
            cat_map[name] = cat

        demo, created = User.objects.get_or_create(
            username='demo',
            defaults={'email': 'demo@campus.edu'},
        )
        if created:
            demo.set_password('12345')
            demo.save()
            UserProfile.objects.get_or_create(user=demo, defaults={'campus': '示例校区'})

        samples = [
            ('二食堂麻辣香锅', '食堂', '二食堂一楼靠左', '18-22元', '分量足，辣度可调，中午11:30前去不用排队太久。'),
            ('黄焖鸡米饭', '外卖', '东门美食街 B12', '15元', '外卖20分钟到，米饭免费加，汤汁拌饭很香。'),
            ('牛肉粉丝汤', '小吃街', '北门小吃街中段', '12元', '汤鲜粉软，适合天冷或没胃口的时候。'),
            ('全家饭团+酸奶', '便利店', '图书馆一楼便利店', '10元', '赶课必备，拿完就走，不用等。'),
            ('轻食沙拉碗', '轻食', '学生活动中心负一层', '22元', '低卡高蛋白，女生聚餐常选这家。'),
        ]
        for title, cat_name, loc, price, desc in samples:
            if LunchPost.objects.filter(title=title, author=demo).exists():
                continue
            LunchPost.objects.create(
                title=title,
                category=cat_map.get(cat_name),
                location=loc,
                price=price,
                description=desc,
                author=demo,
            )

        self.stdout.write(self.style.SUCCESS('干饭情报局示例数据已就绪（演示账号 demo / 12345）'))

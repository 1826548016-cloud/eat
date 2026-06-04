from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='手机号')
    campus = models.CharField(max_length=100, blank=True, null=True, verbose_name='校区/院系')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='头像')
    is_banned = models.BooleanField(default=False, verbose_name='封号')
    is_muted = models.BooleanField(default=False, verbose_name='禁言')
    login_restricted = models.BooleanField(default=False, verbose_name='限制登录')
    is_beta_tester = models.BooleanField(default=False, verbose_name='内测用户')
    auth_token_version = models.PositiveIntegerField(default=0, verbose_name='认证令牌版本')
    moderation_note = models.CharField(max_length=500, blank=True, verbose_name='处罚说明')
    moderated_at = models.DateTimeField(null=True, blank=True, verbose_name='处罚时间')
    moderated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='moderation_actions', verbose_name='处罚操作人',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '用户信息'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.user.username


class FoodCategory(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name='分类名称')
    icon = models.CharField(max_length=20, blank=True, default='🍱', verbose_name='图标')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '情报分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order']

    def __str__(self):
        return self.name


class LunchPost(models.Model):
    title = models.CharField(max_length=120, verbose_name='店名/菜品')
    category = models.ForeignKey(
        FoodCategory, on_delete=models.SET_NULL, null=True,
        related_name='posts', verbose_name='分类',
    )
    location = models.CharField(
        max_length=300, verbose_name='详细地址',
        help_text='如：XX大学北门美食街3号铺、一食堂二楼东侧',
    )
    price = models.CharField(max_length=50, blank=True, verbose_name='人均/价格', help_text='如：12元、15-20元')
    image = models.ImageField(upload_to='lunch/', blank=True, null=True, verbose_name='封面图')
    storefront_image = models.ImageField(
        upload_to='lunch/storefront/', blank=True, null=True, verbose_name='商家门头照片',
    )
    description = models.TextField(verbose_name='推荐理由')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lunch_posts', verbose_name='发布者')
    is_edited = models.BooleanField(default=False, verbose_name='已编辑')
    view_count = models.PositiveIntegerField(default=0, verbose_name='浏览量')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='发布时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '干饭情报'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def cover_image(self):
        first = self.photos.order_by('sort_order', 'id').first()
        if first:
            return first.image
        return self.image

    def sync_cover_image(self):
        first = self.photos.order_by('sort_order', 'id').first()
        if first:
            self.image = first.image
            self.save(update_fields=['image'])


class PostImage(models.Model):
    post = models.ForeignKey(
        LunchPost, on_delete=models.CASCADE, related_name='photos', verbose_name='推荐',
    )
    image = models.ImageField(upload_to='lunch/photos/', verbose_name='实拍图')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')

    class Meta:
        verbose_name = '推荐图片'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.post.title} · 图{self.id}'


class PostView(models.Model):
    post = models.ForeignKey(LunchPost, on_delete=models.CASCADE, related_name='view_records', verbose_name='推荐')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_views', verbose_name='浏览用户')
    viewed_at = models.DateTimeField(auto_now_add=True, verbose_name='浏览时间')

    class Meta:
        verbose_name = '浏览记录'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(fields=['post', 'user'], name='unique_post_view_per_user'),
        ]

    def __str__(self):
        return f'{self.user.username} → {self.post.title}'


class Comment(models.Model):
    post = models.ForeignKey(LunchPost, on_delete=models.CASCADE, related_name='comments', verbose_name='推荐')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lunch_comments', verbose_name='评论者')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='replies', verbose_name='回复的评论',
    )
    content = models.TextField(max_length=500, verbose_name='评论内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='评论时间')

    class Meta:
        verbose_name = '评论'
        verbose_name_plural = verbose_name
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user.username}: {self.content[:20]}'


class PostFavorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_favorites', verbose_name='用户')
    post = models.ForeignKey(
        LunchPost, on_delete=models.CASCADE, related_name='favorited_by', verbose_name='推荐',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='收藏时间')

    class Meta:
        verbose_name = '收藏'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_post_favorite'),
        ]

    def __str__(self):
        return f'{self.user.username} → {self.post.title}'


class PostEndorsement(models.Model):
    """用户对情报的「推荐」点赞，计入首页统计图表。"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_endorsements', verbose_name='用户')
    post = models.ForeignKey(
        LunchPost, on_delete=models.CASCADE, related_name='endorsements', verbose_name='情报',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='推荐时间')

    class Meta:
        verbose_name = '用户推荐'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_post_endorsement'),
        ]

    def __str__(self):
        return f'{self.user.username} 推荐 {self.post.title}'


class ContentReport(models.Model):
    TYPE_POST = 'post'
    TYPE_COMMENT = 'comment'
    TYPE_APPEAL = 'appeal'
    REPORT_TYPE_CHOICES = [
        (TYPE_POST, '举报推荐'),
        (TYPE_COMMENT, '举报评论'),
        (TYPE_APPEAL, '账号申诉'),
    ]

    REASON_SPAM = 'spam'
    REASON_ABUSE = 'abuse'
    REASON_FALSE_INFO = 'false_info'
    REASON_PRIVACY = 'privacy'
    REASON_OTHER = 'other'
    REASON_CHOICES = [
        (REASON_SPAM, '广告/刷屏'),
        (REASON_ABUSE, '辱骂/引战'),
        (REASON_FALSE_INFO, '虚假信息'),
        (REASON_PRIVACY, '侵犯隐私'),
        (REASON_OTHER, '其他'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_RESOLVED = 'resolved'
    STATUS_DISMISSED = 'dismissed'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_RESOLVED, '已处理'),
        (STATUS_DISMISSED, '已驳回'),
    ]

    report_type = models.CharField(max_length=10, choices=REPORT_TYPE_CHOICES, verbose_name='类型')
    reporter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='content_reports', verbose_name='提交人',
    )
    post = models.ForeignKey(
        LunchPost, on_delete=models.CASCADE, null=True, blank=True,
        related_name='reports', verbose_name='相关推荐',
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, null=True, blank=True,
        related_name='reports', verbose_name='相关评论',
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name='原因')
    detail = models.TextField(max_length=1000, blank=True, verbose_name='补充说明')
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='状态',
    )
    admin_note = models.CharField(max_length=500, blank=True, verbose_name='处理备注')
    handled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='handled_reports', verbose_name='处理人',
    )
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')

    class Meta:
        verbose_name = '举报/申诉'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_report_type_display()} #{self.id}'


class Announcement(models.Model):
    title = models.CharField(max_length=120, verbose_name='公告标题')
    content = models.TextField(verbose_name='公告内容')
    is_active = models.BooleanField(default=True, verbose_name='是否展示')
    is_pinned = models.BooleanField(default=False, verbose_name='置顶显示')
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='announcements', verbose_name='发布人',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='发布时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '站点公告'
        verbose_name_plural = verbose_name
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title


class FriendLink(models.Model):
    name = models.CharField(max_length=80, verbose_name='站点名称')
    url = models.URLField(max_length=500, verbose_name='链接地址')
    description = models.CharField(max_length=200, blank=True, verbose_name='简介')
    icon = models.CharField(max_length=20, blank=True, default='🔗', verbose_name='图标')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否展示')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '友情链接'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return self.name


class SiteConfig(models.Model):
    """全站开关（单例，pk=1）。"""
    is_site_open = models.BooleanField(default=True, verbose_name='网站开放')
    closed_message_zh = models.TextField(
        blank=True,
        default='网站维护中，暂停对外服务。如需处理事务请使用管理员账号登录后台。',
        verbose_name='关站说明（中文）',
    )
    closed_message_en = models.TextField(
        blank=True,
        default='The site is under maintenance. Only administrators may log in.',
        verbose_name='关站说明（英文）',
    )
    is_beta_mode = models.BooleanField(default=False, verbose_name='内测模式')
    beta_invite_code = models.CharField(max_length=32, blank=True, verbose_name='内测邀请码')
    beta_code_revision = models.PositiveIntegerField(default=0, verbose_name='邀请码版本')
    contact_intro_zh = models.TextField(
        blank=True,
        default='如有违规举报、账号申诉或合作咨询，可通过以下方式联系站点管理员。',
        verbose_name='联系说明（中文）',
    )
    contact_intro_en = models.TextField(
        blank=True,
        default='For reports, appeals, or inquiries, reach the site administrators via:',
        verbose_name='联系说明（英文）',
    )
    contact_email = models.EmailField(blank=True, verbose_name='联系邮箱')
    contact_phone = models.CharField(max_length=30, blank=True, verbose_name='联系电话')
    contact_wechat = models.CharField(max_length=80, blank=True, verbose_name='微信号')
    contact_qq = models.CharField(max_length=30, blank=True, verbose_name='QQ')
    contact_telegram = models.CharField(max_length=80, blank=True, verbose_name='Telegram')
    contact_weibo = models.URLField(blank=True, verbose_name='微博链接')
    contact_xiaohongshu = models.URLField(blank=True, verbose_name='小红书链接')
    contact_github = models.URLField(blank=True, verbose_name='GitHub 链接')
    contact_bilibili = models.URLField(blank=True, verbose_name='B站链接')
    friend_links_intro = models.TextField(
        blank=True,
        default='以下是与本站互相关注或推荐的友好站点，点击即可访问。',
        verbose_name='友链页说明',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='site_config_updates', verbose_name='最后操作人',
    )

    class Meta:
        verbose_name = '站点配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        parts = []
        parts.append('开放' if self.is_site_open else '关站')
        if self.is_beta_mode:
            parts.append('内测')
        return ' · '.join(parts)

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class LoginLog(models.Model):
    LOGIN_USER = 'user'
    LOGIN_ADMIN = 'admin'
    LOGIN_TYPE_CHOICES = [
        (LOGIN_USER, '前台登录'),
        (LOGIN_ADMIN, '管理后台登录'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='login_logs', verbose_name='用户',
    )
    username = models.CharField(max_length=150, verbose_name='登录账号')
    login_type = models.CharField(max_length=10, choices=LOGIN_TYPE_CHOICES, verbose_name='登录类型')
    success = models.BooleanField(default=True, verbose_name='是否成功')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP 地址')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='浏览器/设备')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='登录时间')

    class Meta:
        verbose_name = '登录日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        status = '成功' if self.success else '失败'
        return f'{self.username} · {self.get_login_type_display()} · {status}'


class OperationLog(models.Model):
    ACTION_REGISTER = 'register'
    ACTION_LOGOUT = 'logout'
    ACTION_ADMIN_LOGOUT = 'admin_logout'
    ACTION_POST_CREATE = 'post_create'
    ACTION_POST_EDIT = 'post_edit'
    ACTION_POST_DELETE = 'post_delete'
    ACTION_COMMENT_CREATE = 'comment_create'
    ACTION_REPORT_CREATE = 'report_create'
    ACTION_APPEAL_CREATE = 'appeal_create'
    ACTION_PROFILE_UPDATE = 'profile_update'
    ACTION_PASSWORD_CHANGE = 'password_change'
    ACTION_ADMIN_USER_DELETE = 'admin_user_delete'
    ACTION_ADMIN_POST_DELETE = 'admin_post_delete'
    ACTION_ADMIN_POST_EDIT = 'admin_post_edit'
    ACTION_ADMIN_COMMENT_DELETE = 'admin_comment_delete'
    ACTION_ADMIN_REPORT_HANDLE = 'admin_report_handle'
    ACTION_ADMIN_STAFF_CREATE = 'admin_staff_create'
    ACTION_ADMIN_STAFF_REMOVE = 'admin_staff_remove'
    ACTION_ADMIN_STAFF_RESET_PASSWORD = 'admin_staff_reset_password'
    ACTION_ADMIN_CATEGORY_ADD = 'admin_category_add'
    ACTION_ADMIN_CATEGORY_EDIT = 'admin_category_edit'
    ACTION_ADMIN_CATEGORY_DELETE = 'admin_category_delete'
    ACTION_ADMIN_PASSWORD_CHANGE = 'admin_password_change'
    ACTION_ADMIN_ANNOUNCEMENT_ADD = 'admin_announcement_add'
    ACTION_ADMIN_ANNOUNCEMENT_EDIT = 'admin_announcement_edit'
    ACTION_ADMIN_ANNOUNCEMENT_DELETE = 'admin_announcement_delete'
    ACTION_ADMIN_SITE_CLOSE = 'admin_site_close'
    ACTION_ADMIN_SITE_OPEN = 'admin_site_open'
    ACTION_ADMIN_BETA_ON = 'admin_beta_on'
    ACTION_ADMIN_BETA_OFF = 'admin_beta_off'
    ACTION_ADMIN_BETA_CODE = 'admin_beta_code'
    ACTION_ADMIN_USER_BAN = 'admin_user_ban'
    ACTION_ADMIN_USER_UNBAN = 'admin_user_unban'
    ACTION_ADMIN_USER_MUTE = 'admin_user_mute'
    ACTION_ADMIN_USER_UNMUTE = 'admin_user_unmute'
    ACTION_ADMIN_USER_RESTRICT_LOGIN = 'admin_user_restrict_login'
    ACTION_ADMIN_USER_ALLOW_LOGIN = 'admin_user_allow_login'
    ACTION_ADMIN_USER_RESET_PASSWORD = 'admin_user_reset_password'
    ACTION_ADMIN_USER_PROFILE_UPDATE = 'admin_user_profile_update'
    ACTION_ADMIN_CONTACT_UPDATE = 'admin_contact_update'
    ACTION_ADMIN_FRIEND_LINK_ADD = 'admin_friend_link_add'
    ACTION_ADMIN_FRIEND_LINK_EDIT = 'admin_friend_link_edit'
    ACTION_ADMIN_FRIEND_LINK_DELETE = 'admin_friend_link_delete'
    ACTION_ADMIN_LOG_DELETE = 'admin_log_delete'

    ACTION_CHOICES = [
        (ACTION_REGISTER, '用户注册'),
        (ACTION_LOGOUT, '用户退出'),
        (ACTION_ADMIN_LOGOUT, '管理员退出'),
        (ACTION_POST_CREATE, '发布推荐'),
        (ACTION_POST_EDIT, '编辑推荐'),
        (ACTION_POST_DELETE, '删除推荐'),
        (ACTION_COMMENT_CREATE, '发表评论'),
        (ACTION_REPORT_CREATE, '提交举报'),
        (ACTION_APPEAL_CREATE, '提交申诉'),
        (ACTION_PROFILE_UPDATE, '更新个人资料'),
        (ACTION_PASSWORD_CHANGE, '修改密码'),
        (ACTION_ADMIN_USER_DELETE, '删除用户'),
        (ACTION_ADMIN_POST_DELETE, '删除推荐(管理)'),
        (ACTION_ADMIN_POST_EDIT, '编辑推荐(管理)'),
        (ACTION_ADMIN_COMMENT_DELETE, '删除评论'),
        (ACTION_ADMIN_REPORT_HANDLE, '处理举报/申诉'),
        (ACTION_ADMIN_STAFF_CREATE, '创建普通管理员'),
        (ACTION_ADMIN_STAFF_REMOVE, '移除普通管理员'),
        (ACTION_ADMIN_STAFF_RESET_PASSWORD, '重置管理员密码'),
        (ACTION_ADMIN_CATEGORY_ADD, '添加分类'),
        (ACTION_ADMIN_CATEGORY_EDIT, '编辑分类'),
        (ACTION_ADMIN_CATEGORY_DELETE, '删除分类'),
        (ACTION_ADMIN_PASSWORD_CHANGE, '管理员改密'),
        (ACTION_ADMIN_ANNOUNCEMENT_ADD, '发布公告'),
        (ACTION_ADMIN_ANNOUNCEMENT_EDIT, '编辑公告'),
        (ACTION_ADMIN_ANNOUNCEMENT_DELETE, '删除公告'),
        (ACTION_ADMIN_SITE_CLOSE, '关闭网站'),
        (ACTION_ADMIN_SITE_OPEN, '开放网站'),
        (ACTION_ADMIN_BETA_ON, '开启内测'),
        (ACTION_ADMIN_BETA_OFF, '关闭内测'),
        (ACTION_ADMIN_BETA_CODE, '更新内测邀请码'),
        (ACTION_ADMIN_USER_BAN, '封禁用户'),
        (ACTION_ADMIN_USER_UNBAN, '解除封号'),
        (ACTION_ADMIN_USER_MUTE, '禁言用户'),
        (ACTION_ADMIN_USER_UNMUTE, '解除禁言'),
        (ACTION_ADMIN_USER_RESTRICT_LOGIN, '限制用户登录'),
        (ACTION_ADMIN_USER_ALLOW_LOGIN, '解除登录限制'),
        (ACTION_ADMIN_USER_RESET_PASSWORD, '重置用户密码'),
        (ACTION_ADMIN_USER_PROFILE_UPDATE, '更新用户资料'),
        (ACTION_ADMIN_CONTACT_UPDATE, '更新联系方式'),
        (ACTION_ADMIN_FRIEND_LINK_ADD, '添加友链'),
        (ACTION_ADMIN_FRIEND_LINK_EDIT, '编辑友链'),
        (ACTION_ADMIN_FRIEND_LINK_DELETE, '删除友链'),
        (ACTION_ADMIN_LOG_DELETE, '删除日志'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='operation_logs', verbose_name='操作用户',
    )
    username = models.CharField(max_length=150, blank=True, verbose_name='用户名快照')
    action = models.CharField(max_length=40, choices=ACTION_CHOICES, verbose_name='操作类型')
    detail = models.CharField(max_length=1000, blank=True, verbose_name='操作详情')
    target_type = models.CharField(max_length=40, blank=True, verbose_name='对象类型')
    target_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='对象 ID')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP 地址')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='浏览器/设备')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        verbose_name = '操作日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.username or "—"} · {self.get_action_display()}'


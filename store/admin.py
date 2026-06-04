from django.contrib import admin
from .models import (
    UserProfile, FoodCategory, LunchPost, PostImage, PostView, Comment,
    Announcement, FriendLink, SiteConfig, LoginLog, OperationLog,
    PostFavorite, ContentReport, PostEndorsement,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'campus', 'is_banned', 'is_muted', 'login_restricted', 'moderated_at',
    )
    list_filter = ('is_banned', 'is_muted', 'login_restricted')
    search_fields = ('user__username', 'campus', 'moderation_note')
    readonly_fields = ('moderated_at', 'moderated_by', 'created_at')


@admin.register(FoodCategory)
class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'sort_order')
    ordering = ('sort_order',)


@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ('post', 'sort_order', 'created_at')
    search_fields = ('post__title',)


@admin.register(LunchPost)
class LunchPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'location', 'author', 'view_count', 'created_at')
    list_filter = ('category',)
    search_fields = ('title', 'location', 'description')
    readonly_fields = ('image',)


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ('is_site_open', 'contact_email', 'updated_at', 'updated_by')
    readonly_fields = ('updated_at',)
    fieldsets = (
        (None, {'fields': ('is_site_open', 'closed_message_zh', 'closed_message_en', 'updated_by', 'updated_at')}),
        ('内测', {'fields': ('is_beta_mode', 'beta_invite_code', 'beta_code_revision')}),
        ('联系管理员', {
            'fields': (
                'contact_intro_zh', 'contact_intro_en',
                'contact_email', 'contact_phone', 'contact_wechat', 'contact_qq',
                'contact_telegram', 'contact_weibo', 'contact_xiaohongshu',
                'contact_github', 'contact_bilibili',
            ),
        }),
        ('友情链接', {'fields': ('friend_links_intro',)}),
    )


@admin.register(FriendLink)
class FriendLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'is_active', 'sort_order', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'url', 'description')
    ordering = ('sort_order', '-created_at')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'is_pinned', 'author', 'created_at')
    list_filter = ('is_active', 'is_pinned')
    search_fields = ('title', 'content')


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'viewed_at')
    list_filter = ('viewed_at',)


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ('username', 'action', 'detail', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('username', 'detail', 'ip_address')
    readonly_fields = ('user', 'username', 'action', 'detail', 'target_type', 'target_id', 'ip_address', 'user_agent', 'created_at')


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ('username', 'login_type', 'success', 'ip_address', 'created_at')
    list_filter = ('login_type', 'success', 'created_at')
    search_fields = ('username', 'ip_address')
    readonly_fields = ('user', 'username', 'login_type', 'success', 'ip_address', 'user_agent', 'created_at')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'parent', 'content', 'created_at')
    search_fields = ('content', 'user__username')


@admin.register(PostFavorite)
class PostFavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    search_fields = ('user__username', 'post__title')


@admin.register(PostEndorsement)
class PostEndorsementAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    search_fields = ('user__username', 'post__title')


@admin.register(ContentReport)
class ContentReportAdmin(admin.ModelAdmin):
    list_display = ('report_type', 'reporter', 'status', 'reason', 'created_at')
    list_filter = ('report_type', 'status', 'reason')
    search_fields = ('reporter__username', 'detail', 'admin_note')

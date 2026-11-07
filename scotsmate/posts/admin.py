from django.contrib import admin
from .models import Post, PostAttachment, PostReaction, PostComment


class PostAttachmentInline(admin.TabularInline):
    model = PostAttachment
    extra = 1


class PostReactionInline(admin.TabularInline):
    model = PostReaction
    extra = 0
    readonly_fields = ('time_reacted',)


class PostCommentInline(admin.TabularInline):
    model = PostComment
    extra = 1
    readonly_fields = ('time_reacted',)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'author', 'created_at', 'updated_at', 'reaction_count', 'comment_count')
    list_filter = ('created_at', 'author')
    search_fields = ('title', 'content', 'author__username', 'author__first_name', 'author__last_name')
    inlines = [PostAttachmentInline, PostReactionInline, PostCommentInline]


@admin.register(PostAttachment)
class PostAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'file_name', 'file')
    search_fields = ('file_name', 'post__title')


@admin.register(PostReaction)
class PostReactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'emp', 'time_reacted')
    list_filter = ('post', 'emp')


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'emp', 'content', 'time_reacted')
    search_fields = ('content', 'emp__username', 'post__title')

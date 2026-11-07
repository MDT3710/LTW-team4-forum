from django.contrib import admin
from .models import StaffProfile, Conversation, ConversationMember, Message, Attachment

class ConversationMemberInline(admin.TabularInline):
    model = ConversationMember
    extra = 1
    autocomplete_fields = ['user']

class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0

@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'position', 'department', 'branch', 'is_online')
    list_filter = ('branch', 'department', 'is_online')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'position', 'department')

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('title_or_type', 'conversation_type', 'group_type', 'branch', 'created_by', 'created_at', 'updated_at')
    list_filter = ('conversation_type', 'group_type', 'branch')
    search_fields = ('title', 'created_by__username', 'created_by__first_name', 'created_by__last_name')
    inlines = [ConversationMemberInline]

    def title_or_type(self, obj):
        return obj.title or f"1-1 ({obj.id})"
    title_or_type.short_description = 'Tên cuộc trò chuyện'

@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'user', 'role', 'is_muted', 'joined_at')
    list_filter = ('role', 'is_muted')
    search_fields = ('conversation__title', 'user__username', 'user__first_name', 'user__last_name')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'conversation', 'short_content', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at', 'conversation__conversation_type')
    search_fields = ('content', 'sender__username', 'conversation__title')
    inlines = [AttachmentInline]

    def short_content(self, obj):
        return (obj.content[:50] + '...') if obj.content else '[Đính kèm tệp]'
    short_content.short_description = 'Nội dung tóm tắt'

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'attachment_type', 'file_size_display', 'message', 'created_at')
    list_filter = ('attachment_type', 'created_at')
    search_fields = ('file_name',)

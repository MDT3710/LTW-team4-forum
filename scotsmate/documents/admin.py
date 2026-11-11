from django.contrib import admin
from .models import DocumentCategory, Document, DocumentUpdateProposal, DocumentAccess


class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'display_order')
    list_display_links = ('id', 'name')
    search_fields = ('name',)


class DocumentAccessInline(admin.TabularInline):
    model = DocumentAccess
    extra = 1
    verbose_name = "Phòng ban được phép xem"
    verbose_name_plural = "Danh sách phòng ban được phép xem (khi chọn Giới hạn theo phòng ban)"


class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'access_scope', 'status', 'request_type', 'creator', 'updated_at')
    list_display_links = ('id', 'title')
    list_filter = ('status', 'request_type', 'access_scope', 'category')
    search_fields = ('title',)
    date_hierarchy = 'updated_at'
    inlines = [DocumentAccessInline]


class DocumentUpdateProposalAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'submitted_by', 'is_processed', 'created_at')


class DocumentAccessAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'department', 'granted_at')
    list_filter = ('department',)
    search_fields = ('document__title', 'department__name')


admin.site.register(DocumentCategory, DocumentCategoryAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(DocumentUpdateProposal, DocumentUpdateProposalAdmin)
admin.site.register(DocumentAccess, DocumentAccessAdmin)

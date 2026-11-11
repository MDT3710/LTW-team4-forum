from django.contrib import admin
from .models import DocumentCategory, Document, DocumentUpdateProposal

class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'display_order')
    list_display_links = ('id', 'name')  # Cho phép bấm vào ID hoặc Tên để sửa
    search_fields = ('name',)

class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'request_type', 'creator', 'updated_at')
    list_filter = ('status', 'request_type', 'category')
    search_fields = ('title',) # Có thể thêm search field giống bookr
    date_hierarchy = 'updated_at' # Có thể thêm tính năng này giống bookr

class DocumentUpdateProposalAdmin(admin.ModelAdmin):
    list_display = ('document', 'submitted_by', 'is_processed', 'created_at')

# Đăng ký các models ở đây, giống như cách bookr làm
admin.site.register(DocumentCategory, DocumentCategoryAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(DocumentUpdateProposal, DocumentUpdateProposalAdmin)
from django.urls import path
from . import views

urlpatterns = [
    # 1. Trang chủ Thư viện tài liệu -> /documents/
    path('', views.document_list, name='documents'),

    # 2. Tạo mới / Đăng tải tài liệu -> /documents/create/
    path('create/', views.document_create, name='document_create'),

    # 3. Tài liệu của tôi & Cập nhật tài liệu -> /documents/my_docs/...
    path('my_docs/', views.document_my_docs, name='document_my_docs'),
    path('my_docs/<int:id>/edit/', views.document_edit, name='document_edit'),

    # 4. Tài liệu chờ duyệt & Chi tiết duyệt -> /documents/approve/...
    path('approve/', views.document_approve_list, name='document_approve'),
    path('approve/<int:id>/', views.document_approve_detail, name='document_approve_detail'),

    # 5. Chi tiết danh mục & Xem trước -> /documents/<cate_id>/...
    path('<str:cate_id>/', views.document_category, name='document_category'),
    path('<str:cate_id>/preview/', views.document_preview, name='document_preview'),
]
from django.db import models
from django.conf import settings
from django.utils.text import slugify

class DocumentCategory(models.Model):
    """
    Bảng 1: Danh mục tài liệu (Hiển thị các thẻ ở trang /documents/)
    Ví dụ: Quy trình làm việc, Đào tạo & Giảng dạy, Nhân sự & Hành chính...
    """
    name = models.CharField("Tên danh mục", max_length=150)
    description = models.TextField("Mô tả ngắn", max_length=500, blank=True)
    display_order = models.PositiveIntegerField("Thứ tự hiển thị", default=0)

    class Meta:
        verbose_name = "Danh mục tài liệu"
        verbose_name_plural = "Danh mục tài liệu"
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class Document(models.Model):
    """
    Bảng 2: Tài liệu (Phục vụ bảng Danh sách, Tài liệu của tôi, Tạo mới, Xem trước)
    """
    STATUS_CHOICES = [
        ('PENDING', 'Chờ duyệt'),
        ('APPROVED', 'Đã duyệt'),
        ('REJECTED', 'Từ chối'),
    ]

    SCOPE_CHOICES = [
        ('ALL', 'Toàn hệ thống'),
        ('HR_ADMIN', 'Khối Hành chính - Nhân sự'),
        ('TRAINING', 'Khối Đào tạo & Học thuật'),
        ('BRANCH', 'Nội bộ chi nhánh'),
    ]

    REQUEST_TYPE_CHOICES = [
        ('NEW', 'Tạo mới'),
        ('UPDATE', 'Cập nhật'),
    ]

    title = models.CharField("Tiêu đề tài liệu", max_length=255)
    code = models.CharField("Mã tài liệu", max_length=50, blank=True, null=True)
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name="Danh mục"
    )
    description = models.TextField("Mô tả nội dung", blank=True)
    file = models.FileField("Tệp tài liệu (PDF/DOCX/PPTX)", upload_to='documents/%Y/%m/')
    access_scope = models.CharField(
        "Phạm vi truy cập",
        max_length=30,
        choices=SCOPE_CHOICES,
        default='ALL'
    )

    # Người tạo & Người duyệt
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_documents',
        verbose_name="Người tạo"
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_documents',
        verbose_name="Người duyệt (Trưởng phòng)"
    )

    # Trạng thái phê duyệt
    status = models.CharField(
        "Trạng thái",
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    request_type = models.CharField(
        "Tình trạng gửi duyệt",
        max_length=20,
        choices=REQUEST_TYPE_CHOICES,
        default='NEW'
    )
    rejection_reason = models.TextField("Lý do từ chối", blank=True, null=True)

    # Thời gian (Phục vụ cột 'Ngày tạo' và 'Lần cập nhật gần nhất')
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Lần cập nhật gần nhất", auto_now=True)
    approved_at = models.DateTimeField("Ngày duyệt", null=True, blank=True)

    class Meta:
        verbose_name = "Tài liệu"
        verbose_name_plural = "Tài liệu"
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class DocumentUpdateProposal(models.Model):
    """
    Bảng 3: Bản đề xuất cập nhật tài liệu
    Dùng cho màn hình 'Cập nhật tài liệu' (/my_docs/{id}/edit)
    và màn hình so sánh 2 cột 'Thông tin hiện tại' vs 'Thông tin đề xuất' (/approve/{id})
    """
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='proposals',
        verbose_name="Tài liệu gốc"
    )
    proposed_title = models.CharField("Tiêu đề đề xuất", max_length=255)
    proposed_category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Danh mục đề xuất"
    )
    proposed_file = models.FileField("Tệp mới cập nhật", upload_to='documents/proposals/%Y/%m/')
    proposed_scope = models.CharField(
        "Phạm vi đề xuất",
        max_length=30,
        choices=Document.SCOPE_CHOICES,
        default='ALL'
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Người gửi cập nhật"
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='proposals_to_approve',
        verbose_name="Trưởng phòng duyệt"
    )
    is_processed = models.BooleanField("Đã xử lý duyệt", default=False)
    created_at = models.DateTimeField("Ngày gửi", auto_now_add=True)

    class Meta:
        verbose_name = "Đề xuất cập nhật tài liệu"
        verbose_name_plural = "Đề xuất cập nhật tài liệu"
        ordering = ['-created_at']

    def __str__(self):
        return self.proposed_title
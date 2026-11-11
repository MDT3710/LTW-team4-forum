from django.db import models
from django.conf import settings
from django.utils import timezone


class DocumentCategory(models.Model):
    """
    Bảng 1: Danh mục tài liệu (Hiển thị các thẻ ở trang /documents/)
    """
    name = models.CharField("Tên danh mục", max_length=150)
    code = models.CharField("Mã danh mục", max_length=150, unique=True, blank=True)
    icon_name = models.CharField("Tên biểu tượng (Icon)", max_length=100, default='folder', blank=True)
    description = models.TextField("Mô tả ngắn", max_length=500, blank=True)
    display_order = models.PositiveIntegerField("Thứ tự hiển thị", default=0)
    created_time = models.DateTimeField("Thời gian tạo", default=timezone.now, blank=True)

    class Meta:
        verbose_name = "Danh mục tài liệu"
        verbose_name_plural = "Danh mục tài liệu"
        ordering = ['display_order', 'name']

    def save(self, *args, **kwargs):
        if not self.code:
            import uuid
            self.code = f"DM-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Document(models.Model):
    """
    Bảng 2: Tài liệu
    """
    STATUS_CHOICES = [
        ('PENDING', 'Chờ duyệt'),
        ('APPROVED', 'Đã duyệt'),
        ('REJECTED', 'Từ chối'),
    ]

    SCOPE_CHOICES = [
        ('ALL', 'Toàn hệ thống'),
        ('DEPARTMENT', 'Giới hạn theo phòng ban'),
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

    # Thời gian
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


class DocumentAccess(models.Model):
    """
    Bảng 4: Cho phép phòng ban nào được truy cập tài liệu
    """
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='access_permissions',
        verbose_name="Tài liệu"
    )
    department = models.ForeignKey(
        'home.Department',
        on_delete=models.CASCADE,
        related_name='accessible_documents',
        verbose_name="Phòng ban được phép truy cập"
    )
    granted_at = models.DateTimeField("Ngày cấp quyền", auto_now_add=True)

    class Meta:
        db_table = 'documents_access'
        verbose_name = "Quyền truy cập tài liệu"
        verbose_name_plural = "Phân quyền truy cập tài liệu"
        unique_together = ('document', 'department')

    def __str__(self):
        return f"{self.document.title} - {self.department.name}"
from django.db import models
from django.contrib.auth.models import User
import os

class StaffProfile(models.Model):
    """
    Thông tin nhân viên / hồ sơ người dùng trong hệ thống Scots English.
    Khớp với danh sách nhân viên chọn trong tạo nhóm & chat cá nhân trên Figma.
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile',
        verbose_name='Tài khoản người dùng'
    )
    department = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name='Phòng ban',
        help_text='Ví dụ: Phòng Đào tạo, Phòng Nhân sự, Tư vấn tuyển sinh'
    )
    position = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name='Chức danh / Vị trí',
        help_text='Ví dụ: Trainer, Giáo viên, Quản lý chi nhánh, Tư vấn'
    )
    branch = models.CharField(
        max_length=100, 
        default='Chi nhánh Cầu Giấy', 
        verbose_name='Chi nhánh',
        help_text='Ví dụ: Chi nhánh Cầu Giấy, Chi nhánh Hà Đông, Chi nhánh Đống Đa'
    )
    avatar = models.ImageField(
        upload_to='avatars/', 
        blank=True, 
        null=True, 
        verbose_name='Ảnh đại diện'
    )
    avatar_color = models.CharField(
        max_length=50, 
        default='bg-blue-100 text-[#134c81]', 
        verbose_name='Màu nền avatar (Tailwind class)',
        help_text='Ví dụ: bg-blue-100 text-[#134c81], bg-emerald-100 text-emerald-800'
    )
    is_online = models.BooleanField(
        default=False, 
        verbose_name='Đang trực tuyến'
    )

    class Meta:
        verbose_name = 'Hồ sơ nhân viên'
        verbose_name_plural = 'Danh sách nhân viên'

    def __str__(self):
        full_name = self.user.get_full_name() or self.user.username
        pos = f" - {self.position}" if self.position else ""
        return f"{full_name}{pos}"

    def get_initials(self):
        """Lấy 2 chữ cái đầu viết tắt cho avatar tròn (ví dụ: Trần Minh Đức -> MD)"""
        full_name = self.user.get_full_name()
        if full_name:
            parts = full_name.strip().split()
            if len(parts) >= 2:
                return f"{parts[-2][0]}{parts[-1][0]}".upper()
            elif len(parts) == 1:
                return parts[0][:2].upper()
        return self.user.username[:2].upper()


class Conversation(models.Model):
    """
    Cuộc trò chuyện: Có thể là Nhóm trò chuyện (GROUP) hoặc Nhắn tin trực tiếp 1-1 (DIRECT).
    """
    TYPE_DIRECT = 'DIRECT'
    TYPE_GROUP = 'GROUP'
    CONVERSATION_TYPE_CHOICES = [
        (TYPE_DIRECT, 'Trực tiếp 1-1'),
        (TYPE_GROUP, 'Nhóm trò chuyện'),
    ]

    GROUP_TYPE_INTERNAL = 'INTERNAL'
    GROUP_TYPE_WORK = 'WORK'
    GROUP_TYPE_CHOICES = [
        (GROUP_TYPE_INTERNAL, 'Nhóm nội bộ'),
        (GROUP_TYPE_WORK, 'Nhóm công việc'),
    ]

    title = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name='Tên cuộc trò chuyện / Tên nhóm',
        help_text='Dành cho nhóm, ví dụ: Tư vấn Cầu Giấy, Đào tạo Chăm sóc học viên'
    )
    conversation_type = models.CharField(
        max_length=10, 
        choices=CONVERSATION_TYPE_CHOICES, 
        default=TYPE_DIRECT,
        verbose_name='Loại trò chuyện'
    )
    group_type = models.CharField(
        max_length=20, 
        choices=GROUP_TYPE_CHOICES, 
        default=GROUP_TYPE_INTERNAL, 
        blank=True, 
        null=True,
        verbose_name='Phân loại nhóm (Hiển thị badge)',
        help_text='Ví dụ: Nhóm nội bộ'
    )
    branch = models.CharField(
        max_length=100, 
        default='Chi nhánh Cầu Giấy', 
        blank=True, 
        null=True,
        verbose_name='Chi nhánh phụ trách'
    )
    avatar = models.ImageField(
        upload_to='conversation_avatars/', 
        blank=True, 
        null=True, 
        verbose_name='Ảnh đại diện nhóm'
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_conversations',
        verbose_name='Người tạo / Quản trị viên'
    )
    members = models.ManyToManyField(
        User, 
        through='ConversationMember', 
        related_name='conversations',
        verbose_name='Các thành viên tham gia'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Cập nhật lần cuối')

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Cuộc trò chuyện'
        verbose_name_plural = 'Danh sách cuộc trò chuyện'

    def __str__(self):
        if self.conversation_type == self.TYPE_GROUP:
            return self.title or f"Nhóm #{self.id}"
        return f"Hội thoại 1-1 #{self.id}"

    @property
    def is_group(self):
        return self.conversation_type == self.TYPE_GROUP

    def get_initials(self):
        """Lấy 2 chữ cái viết tắt cho avatar nhóm (ví dụ: Tư vấn Cầu Giấy -> TV, Đào tạo -> ĐT)"""
        if self.title:
            words = self.title.strip().split()
            if len(words) >= 2:
                return f"{words[0][0]}{words[1][0]}".upper()
            elif len(words) == 1:
                return words[0][:2].upper()
        return "SC"

    def get_other_user(self, current_user):
        """Dành cho chat 1-1: Lấy user đối phương trong cuộc trò chuyện"""
        if self.conversation_type == self.TYPE_DIRECT:
            return self.members.exclude(id=current_user.id).first()
        return None

    def get_latest_message(self):
        """Lấy tin nhắn mới nhất trong cuộc trò chuyện"""
        return self.messages.order_by('-created_at').first()

    def count_members(self):
        return self.members.count()


class ConversationMember(models.Model):
    """
    Bảng trung gian quản lý thành viên trong từng cuộc trò chuyện,
    kèm quyền hạn (Admin / Member) và trạng thái Tắt thông báo.
    """
    ROLE_ADMIN = 'ADMIN'
    ROLE_MEMBER = 'MEMBER'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Quản trị viên'),
        (ROLE_MEMBER, 'Thành viên'),
    ]

    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE, 
        related_name='memberships',
        verbose_name='Cuộc trò chuyện'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='chat_memberships',
        verbose_name='Thành viên'
    )
    role = models.CharField(
        max_length=10, 
        choices=ROLE_CHOICES, 
        default=ROLE_MEMBER,
        verbose_name='Vai trò trong nhóm'
    )
    is_muted = models.BooleanField(
        default=False, 
        verbose_name='Tắt thông báo',
        help_text='Khớp với nút chức năng Tắt thông báo trên Figma'
    )
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian tham gia')
    last_read_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='Thời điểm xem tin nhắn cuối cùng',
        help_text='Dùng để tính số tin nhắn mới chưa đọc (ví dụ: 2 tin mới)'
    )

    class Meta:
        unique_together = ('conversation', 'user')
        verbose_name = 'Thành viên cuộc trò chuyện'
        verbose_name_plural = 'Danh sách thành viên cuộc trò chuyện'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()}) - {self.conversation}"


class Message(models.Model):
    """
    Tin nhắn trong cuộc trò chuyện (Hỗ trợ tin nhắn văn bản và đính kèm file).
    """
    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE, 
        related_name='messages',
        verbose_name='Cuộc trò chuyện'
    )
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_messages',
        verbose_name='Người gửi'
    )
    content = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='Nội dung tin nhắn'
    )
    is_read = models.BooleanField(
        default=False, 
        verbose_name='Đã xem',
        help_text='Trạng thái hiển thị Đã xem trên Figma'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian gửi')

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Tin nhắn'
        verbose_name_plural = 'Danh sách tin nhắn'

    def __str__(self):
        sender_name = self.sender.get_full_name() or self.sender.username
        snippet = (self.content[:40] + '...') if self.content else '[Đính kèm file]'
        return f"{sender_name}: {snippet}"

    def has_attachments(self):
        return self.attachments.exists()


class Attachment(models.Model):
    """
    File đính kèm trong tin nhắn.
    Phục vụ trực tiếp cho mục 'File phương tiện và file' ở cột bên phải trên Figma.
    """
    TYPE_MEDIA = 'MEDIA'
    TYPE_DOCUMENT = 'DOCUMENT'
    ATTACHMENT_TYPE_CHOICES = [
        (TYPE_MEDIA, 'File phương tiện (Hình ảnh / Video)'),
        (TYPE_DOCUMENT, 'File tài liệu (PDF, Word, Excel, ...)'),
    ]

    message = models.ForeignKey(
        Message, 
        on_delete=models.CASCADE, 
        related_name='attachments',
        verbose_name='Thuộc tin nhắn'
    )
    file = models.FileField(
        upload_to='attachments/%Y/%m/', 
        verbose_name='Tệp đính kèm'
    )
    file_name = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name='Tên hiển thị file',
        help_text='Ví dụ: Huong-dan-workshop.pdf, Tinh-huong-CSHV.pdf'
    )
    file_size_display = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name='Kích thước hiển thị',
        help_text='Ví dụ: 320 KB, 1.2 MB'
    )
    attachment_type = models.CharField(
        max_length=15, 
        choices=ATTACHMENT_TYPE_CHOICES, 
        default=TYPE_DOCUMENT,
        verbose_name='Loại tệp'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian tải lên')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tệp đính kèm'
        verbose_name_plural = 'Danh sách tệp đính kèm'

    def __str__(self):
        return self.file_name or os.path.basename(self.file.name)

    def save(self, *args, **kwargs):
        # Tự động lấy tên file nếu chưa điền
        if not self.file_name and self.file:
            self.file_name = os.path.basename(self.file.name)

        # Tự động phân loại (ảnh -> MEDIA, pdf/doc -> DOCUMENT)
        if self.file_name:
            ext = os.path.splitext(self.file_name)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4']:
                self.attachment_type = self.TYPE_MEDIA
            else:
                self.attachment_type = self.TYPE_DOCUMENT

        # Tự động tính kích thước hiển thị dạng KB / MB
        if not self.file_size_display and self.file:
            try:
                size_bytes = self.file.size
                if size_bytes < 1024 * 1024:
                    self.file_size_display = f"{size_bytes / 1024:.0f} KB"
                else:
                    self.file_size_display = f"{size_bytes / (1024 * 1024):.1f} MB"
            except Exception:
                pass

        super().save(*args, **kwargs)

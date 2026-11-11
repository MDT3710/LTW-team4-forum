from django.db import models
from django.conf import settings
from django.utils import timezone
from home.models import Branch, Department


class Event(models.Model):
    """
    Bảng: events_event
    Đại diện cho các sự kiện nội bộ, đào tạo, hội thảo, giao lưu thể thao và văn hóa Scots English.
    """
    CATEGORY_TRAINING = 'training'
    CATEGORY_WORKSHOP = 'workshop'
    CATEGORY_CULTURE = 'culture'
    CATEGORY_SPORTS = 'sports'
    CATEGORY_CEREMONY = 'ceremony'
    CATEGORY_GENERAL = 'general'

    CATEGORY_CHOICES = [
        (CATEGORY_TRAINING, 'Đào tạo nội bộ'),
        (CATEGORY_WORKSHOP, 'Hội thảo học thuật'),
        (CATEGORY_CULTURE, 'Văn hóa & Gắn kết'),
        (CATEGORY_SPORTS, 'Thể thao Scots'),
        (CATEGORY_CEREMONY, 'Lễ hội & Tôn vinh'),
        (CATEGORY_GENERAL, 'Sự kiện chung'),
    ]

    STATUS_UPCOMING = 'upcoming'
    STATUS_ONGOING = 'ongoing'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_UPCOMING, 'Sắp diễn ra'),
        (STATUS_ONGOING, 'Đang diễn ra'),
        (STATUS_COMPLETED, 'Đã kết thúc'),
        (STATUS_CANCELLED, 'Đã hủy'),
    ]

    title = models.CharField(max_length=255, verbose_name="Tên sự kiện")
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_TRAINING,
        verbose_name="Phân loại sự kiện"
    )
    description = models.TextField(verbose_name="Mô tả sự kiện")
    agenda = models.TextField(blank=True, default='', verbose_name="Lịch trình chi tiết (Agenda)")
    
    date_start = models.DateTimeField(verbose_name="Thời gian bắt đầu")
    date_end = models.DateTimeField(verbose_name="Thời gian kết thúc")
    
    location = models.CharField(max_length=255, verbose_name="Địa điểm tổ chức")
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        verbose_name="Chi nhánh áp dụng"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        verbose_name="Phòng ban chủ trì"
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organized_events',
        verbose_name="Người phụ trách / Diễn giả"
    )
    
    max_participants = models.PositiveIntegerField(
        default=50,
        verbose_name="Số lượng đăng ký tối đa"
    )
    banner = models.ImageField(
        upload_to='events/banners/',
        null=True,
        blank=True,
        verbose_name="Ảnh bìa sự kiện"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_UPCOMING,
        verbose_name="Trạng thái"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        db_table = 'events_event'
        verbose_name = "Sự kiện nội bộ"
        verbose_name_plural = "Danh sách sự kiện nội bộ"
        ordering = ['date_start']

    def __str__(self):
        return self.title

    @property
    def total_registered(self):
        return self.registrations.count()

    @property
    def is_full(self):
        return self.total_registered >= self.max_participants

    @property
    def available_slots(self):
        return max(0, self.max_participants - self.total_registered)

    @property
    def is_past(self):
        return self.date_end < timezone.now()

    @property
    def category_badge_class(self):
        classes = {
            self.CATEGORY_TRAINING: 'bg-blue-100 text-[#134c81]',
            self.CATEGORY_WORKSHOP: 'bg-emerald-100 text-emerald-800',
            self.CATEGORY_CULTURE: 'bg-purple-100 text-purple-800',
            self.CATEGORY_SPORTS: 'bg-amber-100 text-amber-800',
            self.CATEGORY_CEREMONY: 'bg-rose-100 text-rose-800',
            self.CATEGORY_GENERAL: 'bg-slate-100 text-slate-800',
        }
        return classes.get(self.category, 'bg-slate-100 text-slate-800')


class EventRegistration(models.Model):
    """
    Bảng: events_registration
    Quản lý việc nhân sự đăng ký và điểm danh tham gia các sự kiện.
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='registrations',
        verbose_name="Sự kiện"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_registrations',
        verbose_name="Nhân viên tham gia"
    )
    registered_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm đăng ký")
    attended = models.BooleanField(default=False, verbose_name="Đã tham gia / Điểm danh")
    note = models.CharField(max_length=255, blank=True, default='', verbose_name="Ghi chú cá nhân")

    class Meta:
        db_table = 'events_registration'
        unique_together = ('event', 'user')
        verbose_name = "Đăng ký sự kiện"
        verbose_name_plural = "Danh sách đăng ký sự kiện"
        ordering = ['-registered_at']

    def __str__(self):
        return f"{self.user.username} - {self.event.title}"

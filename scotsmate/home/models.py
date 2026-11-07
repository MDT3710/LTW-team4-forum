from django.core.validators import MinLengthValidator
from django.db import models
from django.conf import settings


class Branch(models.Model):
    class RegionChoices(models.TextChoices):
        NORTH = 'NORTH', 'Miền Bắc'
        CENTRAL = 'CENTRAL', 'Miền Trung'
        SOUTH = 'SOUTH', 'Miền Nam'
    name = models.CharField(max_length=255, verbose_name="Tên chi nhánh")
    region = models.CharField(
        max_length=20,
        choices=RegionChoices.choices,
        verbose_name="Khu vực"
    )
    class Meta:
        db_table = 'branch'

    def __str__(self) -> str:
        return self.name


class Department(models.Model):
    class BlockChoices(models.TextChoices):
        LEGAL_HR = 'LEGAL AND HR', 'Khối Hành Chính - Nhân Sự'
        FINANCE = 'FINANCE', 'Khối Tài Chính - Kế toán'
        OPERATION = 'OPERATION', 'Khối Vận Hành'
        ACADEMY = 'ACADEMY', 'Khối Học Thuật'
        TECHNOLOGY = 'TECHNOLOGY', 'Khối Công Nghệ Thông Tin'
        MKT_SALE = 'MARKETING AND SALE', 'Khối Marketing và Kinh Doanh'
        CENTRAL = 'CENTRAL', 'Khối Trung Tâm'

    name = models.CharField(
        max_length=100,
        verbose_name="Tên phòng ban")
    manager = models.ForeignKey(
        'EmployeeInformation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments',
        verbose_name="Trưởng phòng"
    )
    block = models.CharField(
        max_length=50,
        choices=BlockChoices.choices,
        blank=True,
        null=True,
        verbose_name="Khối"
    )

    class Meta:
        db_table = 'department'

    def __str__(self) -> str:
        return self.name


class EmployeeInformation(models.Model):
    # Bảng thông tin chi tiết nhân viên (employee_information).
    # `emp_id` đóng vai trò vừa là PK vừa là FK nối 1-1 tới User hệ thống.
    class GenderChoices(models.TextChoices):
        MALE = 'MALE', 'Nam'
        FEMALE = 'FEMALE', 'Nữ'
        OTHER = 'OTHER', 'Khác'

    class StatusChoices(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Đang hoạt động'
        PROBATION = 'PROBATION', 'Thử việc'
        ON_LEAVE = 'ON_LEAVE', 'Nghỉ phép'
        RESIGNED = 'RESIGNED', 'Đã nghỉ việc'

    emp_id = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='emp_id',
        related_name='employee_info',
        verbose_name="Tài khoản người dùng"
    )
    gender = models.CharField(
        max_length=10,
        choices=GenderChoices.choices,
        verbose_name="Giới tính"
    )
    NIN = models.CharField(
        max_length=12,
        validators=[
            MinLengthValidator(12, message="Số CCCD phải có đúng 12 ký tự.")
        ],
        unique=True,
        verbose_name="Căn cước công dân"
    )

    tel = models.CharField(
        max_length=15, # chấp nhận sdt quốc tế
        verbose_name="Số điện thoại"
    )
    email = models.EmailField(
        verbose_name="Email"
    )
    dep = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='department',
        related_name='employees',
        verbose_name="Phòng ban"
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='branch',
        related_name='employees',
        verbose_name="Chi nhánh"
    )
    date_of_birth = models.DateField(
        verbose_name="Ngày sinh"
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
        verbose_name="Trạng thái làm việc"
    )

    class Meta:
        db_table = 'employee_information'

    def __str__(self) -> str:
        return self.emp_id.username
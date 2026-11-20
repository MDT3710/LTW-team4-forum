from urllib.parse import urlparse
from django.contrib import messages
from django.contrib.auth.models import Group
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

ROLE_ADMIN = 'Admin'
ROLE_MANAGER = 'Trưởng phòng'
ROLE_TRAINER = 'Trainer'
ROLE_EMPLOYEE = 'Nhân viên'

ALL_ROLE_GROUPS = (
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_TRAINER,
    ROLE_EMPLOYEE,
)


def _get_emp_dep(user):
    try:
        emp_info = getattr(user, 'employee_info', None)
        return getattr(emp_info, 'dep', None) if emp_info else None
    except Exception:
        return None


def _user_role_group_names(user):
    if not user or not user.is_authenticated:
        return set()
    return set(user.groups.filter(name__in=ALL_ROLE_GROUPS).values_list('name', flat=True))


def is_it_admin(user):
    """Admin hệ thống (Phòng Phát triển & vận hành ứng dụng) - full quyền toàn bộ 7 module và /admin/."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role_groups = _user_role_group_names(user)
    if role_groups:
        return ROLE_ADMIN in role_groups
    dep = _get_emp_dep(user)
    return bool(dep and dep.name == 'Phát triển & vận hành ứng dụng')


def is_department_manager(user):
    """Trưởng phòng - quản lý tài liệu, khảo sát, sự kiện và nhóm chat."""
    if not user or not user.is_authenticated or is_it_admin(user):
        return False
    from home.models import Department
    role_groups = _user_role_group_names(user)
    if ROLE_MANAGER in role_groups:
        return True
    return Department.objects.filter(manager=user).exists()


def is_trainer(user):
    """Trainer - giảng viên phụ trách đào tạo nhân sự (KHÔNG dựa vào is_staff)."""
    if not user or not user.is_authenticated or is_it_admin(user):
        return False
    from home.models import Department
    from courses.models import Course, CourseAccess

    role_groups = _user_role_group_names(user)
    if ROLE_TRAINER in role_groups:
        return True
    if Department.objects.filter(name='Đào tạo', manager=user).exists():
        return True
    if CourseAccess.objects.filter(emp=user, role__in=['trainer', 'assistant', 'manager']).exists():
        return True
    if Course.objects.filter(creator=user).exists():
        return True
    return False


def is_official_staff(user):
    """is_staff=1 xác nhận nhân viên chính thức; is_staff=0 là cộng tác viên part-time."""
    return bool(user and user.is_authenticated and user.is_staff)


def get_primary_role_label(user):
    if not user or not user.is_authenticated:
        return 'Khách'
    if is_it_admin(user):
        return 'Admin'
    mgr = is_department_manager(user)
    trn = is_trainer(user)
    if mgr and trn:
        return 'Trưởng phòng · Trainer'
    if mgr:
        return 'Trưởng phòng'
    if trn:
        return 'Giảng viên (Trainer)'
    if not user.is_staff:
        return 'Cộng tác viên (Part-time)'
    return 'Nhân viên'


def get_user_roles_context(user):
    if not user or not user.is_authenticated:
        return {
            'is_it_admin': False,
            'is_department_manager': False,
            'is_trainer': False,
            'is_official_staff': False,
            'primary_role_label': 'Khách',
        }
    return {
        'is_it_admin': is_it_admin(user),
        'is_department_manager': is_department_manager(user),
        'is_trainer': is_trainer(user),
        'is_official_staff': is_official_staff(user),
        'primary_role_label': get_primary_role_label(user),
    }


def redirect_back_with_error(request, message, fallback_url='home'):
    """Ngăn chặn truy cập trái phép và điều hướng người dùng quay trở lại trang hiện tại (hoặc fallback)."""
    messages.error(request, message)
    referer = request.META.get('HTTP_REFERER', '')
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        ref_path = urlparse(referer).path
        if ref_path and ref_path != request.path:
            return redirect(referer)
    return redirect(fallback_url)


def ensure_role_groups():
    return {name: Group.objects.get_or_create(name=name)[0] for name in ALL_ROLE_GROUPS}

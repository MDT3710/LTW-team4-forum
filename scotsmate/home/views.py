from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from posts.models import Post, PostReaction
from .models import Department, Branch, EmployeeInformation
from .roles import (
    is_it_admin,
    redirect_back_with_error,
    ensure_role_groups,
    get_primary_role_label,
    ROLE_ADMIN,
    ROLE_DIRECTOR,
    ROLE_MANAGER,
    ROLE_TRAINER,
    ROLE_EMPLOYEE,
)


def index_view(request):
    """
    Điều hướng khi mở trang web (đường dẫn gốc /):
    - Nếu chưa đăng nhập: Luôn chuyển hướng ngay sang trang đăng nhập (/login/).
    - Sau khi đăng nhập: Chuyển vào Trang chủ Bảng tin (/home/).
    """
    if not request.user.is_authenticated:
        return redirect('login')
    return redirect('home')


def HomeView(request):
    """
    Truy vấn danh sách bài viết từ database để hiển thị Bảng tin (Newfeeds).
    Nếu chưa đăng nhập: chuyển hướng ngay sang trang đăng nhập (/login/).
    Sau khi đăng nhập: nhận diện đúng người dùng đang truy cập (current_user).
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=/home/')

    current_user = request.user

    query = request.GET.get('q', '').strip()
    posts_qs = Post.objects.all().prefetch_related(
        'attachments',
        'reactions',
        'reactions__emp',
        'comments',
        'comments__emp',
        'author'
    )

    # Lọc bài viết theo phạm vi hiển thị thực tế:
    # - 'Toàn công ty': tất cả nhân viên đều thấy
    # - 'Chỉ mình tôi': chỉ chính tác giả mới thấy
    # - 'Phòng ban': chỉ đồng nghiệp cùng phòng ban (hoặc superuser) mới thấy
    from posts.colleagues import get_user_department
    user_dept = get_user_department(current_user)
    same_dept_user_ids = [
        u.id for u in User.objects.all()
        if get_user_department(u) == user_dept
    ]

    vis_filter = (
        Q(visibility=Post.VISIBILITY_COMPANY) |
        Q(visibility='') |
        Q(visibility__isnull=True) |
        Q(author=current_user)
    )
    if is_it_admin(current_user):
        vis_filter |= Q(visibility=Post.VISIBILITY_DEPARTMENT)
    else:
        vis_filter |= Q(visibility=Post.VISIBILITY_DEPARTMENT, author_id__in=same_dept_user_ids)

    posts_qs = posts_qs.filter(vis_filter)

    if query:
        posts_qs = posts_qs.filter(
            Q(content__icontains=query) |
            Q(title__icontains=query) |
            Q(author__first_name__icontains=query) |
            Q(author__last_name__icontains=query) |
            Q(author__username__icontains=query)
        )

    posts = list(posts_qs.order_by('-created_at'))

    # Xác định trạng thái đã like của người dùng hiện tại
    liked_post_ids = set(
        PostReaction.objects.filter(emp=current_user).values_list('post_id', flat=True)
    )

    from posts.views import prepare_post_comments
    from posts.colleagues import get_profile_details
    valid_posts = []
    for post in posts:
        try:
            author = post.author
            if not author:
                continue
            post.is_liked_by_user = post.id in liked_post_ids
            post.author_avatar = get_profile_details(author).get('avatar', '/static/img/profile_avatar_144.png')
            prepare_post_comments(post, current_user.id)
            valid_posts.append(post)
        except Exception:
            continue

    from events.models import Event, EventRegistration
    from courses.models import CourseEnrollment
    from django.utils import timezone
    now = timezone.now()

    # 1. Danh sách sự kiện sắp tới toàn hệ thống
    upcoming_events = list(
        Event.objects.filter(status=Event.STATUS_UPCOMING, date_start__gte=now)
        .order_by('date_start')[:3]
    )
    for ev in upcoming_events:
        ev.is_registered = ev.registrations.filter(user=current_user).exists()

    # 2. Lịch cá nhân của người dùng (Sự kiện đã đăng ký + Khóa học đang tham gia)
    calendar_days_dict = {}

    user_event_regs = (
        EventRegistration.objects.filter(user=current_user, event__date_start__gte=now)
        .select_related('event')
        .order_by('event__date_start')[:4]
    )
    for reg in user_event_regs:
        ev = reg.event
        day_key = timezone.localtime(ev.date_start).strftime('%d/%m')
        if day_key not in calendar_days_dict:
            calendar_days_dict[day_key] = []
        time_str = timezone.localtime(ev.date_start).strftime('%H:%M')
        if ev.date_end:
            time_str += ' – ' + timezone.localtime(ev.date_end).strftime('%H:%M')
        calendar_days_dict[day_key].append({
            'title': ev.title,
            'time': time_str,
            'location': ev.location,
            'url': f'/events/{ev.id}/',
            'type': 'event',
            'icon': 'calendar'
        })

    user_courses = (
        CourseEnrollment.objects.filter(emp=current_user, is_completed=False)
        .select_related('course')
        .order_by('-enrollment_date')[:2]
    )
    for en in user_courses:
        day_key = timezone.localtime(en.course.date_end).strftime('%d/%m') if en.course.date_end else 'Đang học'
        if day_key not in calendar_days_dict:
            calendar_days_dict[day_key] = []
        calendar_days_dict[day_key].append({
            'title': f'Khóa: {en.course.title}',
            'time': 'Bài kiểm tra cuối khóa',
            'location': 'Trực tuyến LMS',
            'url': f'/courses/trainee/courses/{en.course.id}/',
            'type': 'course',
            'icon': 'book'
        })

    if not calendar_days_dict:
        for ev in upcoming_events[:2]:
            day_key = timezone.localtime(ev.date_start).strftime('%d/%m')
            if day_key not in calendar_days_dict:
                calendar_days_dict[day_key] = []
            calendar_days_dict[day_key].append({
                'title': ev.title,
                'time': timezone.localtime(ev.date_start).strftime('%H:%M'),
                'location': ev.location,
                'url': f'/events/{ev.id}/',
                'type': 'suggested_event',
                'icon': 'calendar'
            })

    calendar_schedule = [
        {'date': k, 'items': v}
        for k, v in calendar_days_dict.items()
    ]

    return render(request, 'home.html', {
        'posts': valid_posts,
        'current_user': current_user,
        'search_query': query,
        'upcoming_events': upcoming_events,
        'calendar_schedule': calendar_schedule,
    })


def accounts_manage_view(request):
    """
    Quản lý tài khoản (Chỉ Admin - Phòng Phát triển & vận hành ứng dụng):
    - Xem danh sách tài khoản và thông tin nhân sự
    - Tạo tài khoản mới
    - Cập nhật tài khoản (extend: Cập nhật thông tin hiển thị, Đổi role phân quyền, Vô hiệu/kích hoạt, Xóa)
    Lưu ý: Mật khẩu do nhân viên tự xử lý qua cơ chế Django Built-in PasswordResetView / PasswordChangeView.
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=/accounts/manage/')
    if not is_it_admin(request.user):
        return redirect_back_with_error(
            request,
            'Bạn không có quyền truy cập chức năng Quản lý tài khoản. Chỉ Admin (Phòng IT) mới được phép.',
            fallback_url='home'
        )

    groups = ensure_role_groups()
    departments = Department.objects.all().order_by('id')
    branches = Branch.objects.all().order_by('id')

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        if action == 'create_account':
            username = request.POST.get('username', '').strip().lower()
            password = request.POST.get('password', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            role = request.POST.get('role', ROLE_EMPLOYEE).strip()
            is_official = (request.POST.get('is_staff') == '1')
            dep_id = request.POST.get('department_id')
            branch_id = request.POST.get('branch_id')
            nin = request.POST.get('nin', '').strip()
            tel = request.POST.get('tel', '').strip() or '0900000000'
            dob = request.POST.get('date_of_birth', '').strip() or '1995-01-01'

            if not username or not password:
                messages.error(request, 'Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu khởi tạo.')
                return redirect('accounts_manage')
            if User.objects.filter(username=username).exists():
                messages.error(request, f'Tên đăng nhập "{username}" đã tồn tại.')
                return redirect('accounts_manage')

            with transaction.atomic():
                new_user = User.objects.create_user(
                    username=username,
                    password=password,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
                new_user.is_staff = is_official
                new_user.is_superuser = (role == ROLE_ADMIN)
                new_user.save()

                role_map = {
                    ROLE_ADMIN: [groups[ROLE_ADMIN]],
                    ROLE_DIRECTOR: [groups[ROLE_DIRECTOR]],
                    ROLE_MANAGER: [groups[ROLE_MANAGER], groups[ROLE_EMPLOYEE]],
                    ROLE_TRAINER: [groups[ROLE_TRAINER], groups[ROLE_EMPLOYEE]],
                    ROLE_EMPLOYEE: [groups[ROLE_EMPLOYEE]],
                }
                new_user.groups.set(role_map.get(role, [groups[ROLE_EMPLOYEE]]))

                dep = Department.objects.filter(id=dep_id).first() if dep_id else None
                branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
                if not nin or len(nin) != 12 or EmployeeInformation.objects.filter(NIN=nin).exists():
                    nin = f"0012{new_user.id:08d}"[:12]
                EmployeeInformation.objects.create(
                    emp_id=new_user,
                    gender=EmployeeInformation.GenderChoices.OTHER,
                    NIN=nin,
                    tel=tel,
                    dep=dep,
                    branch=branch,
                    date_of_birth=dob,
                )
                if role == ROLE_MANAGER and dep:
                    dep.manager = new_user
                    dep.save(update_fields=['manager'])

            messages.success(request, f'Đã tạo tài khoản "{username}" ({role}) thành công.')
            return redirect('accounts_manage')

        target_id = request.POST.get('user_id')
        target_user = get_object_or_404(User, id=target_id)

        if action == 'update_account':
            target_user.first_name = request.POST.get('first_name', '').strip()
            target_user.last_name = request.POST.get('last_name', '').strip()
            target_user.email = request.POST.get('email', '').strip()
            target_user.is_staff = (request.POST.get('is_staff') == '1')
            new_role = request.POST.get('role', ROLE_EMPLOYEE).strip()

            if target_user.id == request.user.id and new_role != ROLE_ADMIN:
                messages.error(request, 'Không thể tự hạ quyền Admin của chính tài khoản đang đăng nhập.')
                return redirect('accounts_manage')

            with transaction.atomic():
                target_user.is_superuser = (new_role == ROLE_ADMIN)
                target_user.save()

                role_map = {
                    ROLE_ADMIN: [groups[ROLE_ADMIN]],
                    ROLE_DIRECTOR: [groups[ROLE_DIRECTOR]],
                    ROLE_MANAGER: [groups[ROLE_MANAGER], groups[ROLE_EMPLOYEE]],
                    ROLE_TRAINER: [groups[ROLE_TRAINER], groups[ROLE_EMPLOYEE]],
                    ROLE_EMPLOYEE: [groups[ROLE_EMPLOYEE]],
                }
                target_user.groups.set(role_map.get(new_role, [groups[ROLE_EMPLOYEE]]))

                dep_id = request.POST.get('department_id')
                branch_id = request.POST.get('branch_id')
                dep = Department.objects.filter(id=dep_id).first() if dep_id else None
                branch = Branch.objects.filter(id=branch_id).first() if branch_id else None

                emp_info = getattr(target_user, 'employee_info', None)
                if emp_info:
                    emp_info.dep = dep
                    emp_info.branch = branch
                    tel = request.POST.get('tel', '').strip()
                    if tel:
                        emp_info.tel = tel
                    emp_info.save()

                if new_role == ROLE_MANAGER and dep:
                    dep.manager = target_user
                    dep.save(update_fields=['manager'])
                elif new_role != ROLE_MANAGER:
                    Department.objects.filter(manager=target_user).update(manager=None)

            messages.success(request, f'Đã cập nhật thông tin & phân quyền cho tài khoản "{target_user.username}".')
            return redirect('accounts_manage')

        elif action == 'toggle_active':
            if target_user.id == request.user.id:
                messages.error(request, 'Không thể tự vô hiệu hóa tài khoản đang đăng nhập.')
                return redirect('accounts_manage')
            target_user.is_active = not target_user.is_active
            target_user.save(update_fields=['is_active'])
            state_lbl = 'kích hoạt' if target_user.is_active else 'vô hiệu hóa'
            messages.success(request, f'Đã {state_lbl} tài khoản "{target_user.username}".')
            return redirect('accounts_manage')

        elif action == 'delete_account':
            if target_user.id == request.user.id:
                messages.error(request, 'Không thể tự xóa tài khoản đang đăng nhập.')
                return redirect('accounts_manage')
            uname = target_user.username
            target_user.delete()
            messages.success(request, f'Đã xóa tài khoản "{uname}" khỏi hệ thống.')
            return redirect('accounts_manage')

    query = request.GET.get('q', '').strip()
    users_qs = User.objects.select_related('employee_info__dep', 'employee_info__branch').prefetch_related('groups').order_by('id')
    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    users_list = []
    for u in users_qs:
        gnames = set(u.groups.values_list('name', flat=True))
        if ROLE_ADMIN in gnames or u.is_superuser:
            u.selected_role = ROLE_ADMIN
        elif ROLE_DIRECTOR in gnames:
            u.selected_role = ROLE_DIRECTOR
        elif ROLE_MANAGER in gnames:
            u.selected_role = ROLE_MANAGER
        elif ROLE_TRAINER in gnames:
            u.selected_role = ROLE_TRAINER
        else:
            u.selected_role = ROLE_EMPLOYEE
        u.role_label = get_primary_role_label(u)
        users_list.append(u)

    return render(request, 'accounts_manage.html', {
        'users_list': users_list,
        'departments': departments,
        'branches': branches,
        'search_query': query,
        'role_choices': [ROLE_EMPLOYEE, ROLE_TRAINER, ROLE_MANAGER, ROLE_DIRECTOR, ROLE_ADMIN],
    })

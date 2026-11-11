from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.db.models import Q
from posts.models import Post, PostReaction


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
    if current_user.is_superuser:
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

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.utils import timezone
from .models import Event, EventRegistration
from home.models import Branch, Department


def events_list(request):
    """
    Trang danh sách sự kiện toàn hệ thống Scots English:
    - Tìm kiếm theo từ khóa (tiêu đề, địa điểm, mô tả).
    - Lọc theo phân loại (Đào tạo, Hội thảo, Thể thao, Văn hóa...).
    - Lọc theo chi nhánh và trạng thái.
    - Phân tab: 'all' (Tất cả), 'upcoming' (Sắp diễn ra), 'my' (Sự kiện của tôi), 'past' (Đã kết thúc).
    """
    tab = request.GET.get('tab', 'all')
    category = request.GET.get('category', '')
    branch_id = request.GET.get('branch', '')
    query = request.GET.get('q', '').strip()

    events_qs = Event.objects.select_related('organizer', 'branch', 'department').prefetch_related('registrations')

    now = timezone.now()

    if tab == 'upcoming':
        events_qs = events_qs.filter(date_start__gte=now).exclude(status=Event.STATUS_CANCELLED)
    elif tab == 'my':
        if request.user.is_authenticated:
            events_qs = events_qs.filter(registrations__user=request.user)
    elif tab == 'past':
        events_qs = events_qs.filter(Q(date_end__lt=now) | Q(status=Event.STATUS_COMPLETED))

    if category:
        events_qs = events_qs.filter(category=category)

    if branch_id and branch_id.isdigit():
        events_qs = events_qs.filter(branch_id=int(branch_id))

    if query:
        events_qs = events_qs.filter(
            Q(title__icontains=query) |
            Q(location__icontains=query) |
            Q(description__icontains=query)
        )

    # Đánh dấu trạng thái đã đăng ký của người dùng hiện tại
    user_registered_event_ids = set()
    if request.user.is_authenticated:
        user_registered_event_ids = set(
            EventRegistration.objects.filter(user=request.user).values_list('event_id', flat=True)
        )

    events = list(events_qs.order_by('-date_start'))
    for ev in events:
        ev.is_user_registered = ev.id in user_registered_event_ids

    branches = Branch.objects.all().order_by('name')

    # Thống kê số lượng
    counts = {
        'all': Event.objects.count(),
        'upcoming': Event.objects.filter(date_start__gte=now).count(),
        'my': EventRegistration.objects.filter(user=request.user).count() if request.user.is_authenticated else 0,
        'past': Event.objects.filter(date_end__lt=now).count(),
    }

    return render(request, 'events_list.html', {
        'events': events,
        'branches': branches,
        'current_tab': tab,
        'selected_category': category,
        'selected_branch': branch_id,
        'search_query': query,
        'counts': counts,
        'category_choices': Event.CATEGORY_CHOICES,
    })


def event_detail(request, event_id):
    """
    Trang chi tiết sự kiện:
    - Toàn bộ thông tin: Tiêu đề, Thời gian, Địa điểm, Diễn giả, Nội dung, Lịch trình (Agenda).
    - Danh sách người tham dự.
    - Nút Đăng ký / Hủy đăng ký.
    """
    event = get_object_or_404(
        Event.objects.select_related('organizer', 'branch', 'department'),
        id=event_id
    )

    is_registered = False
    if request.user.is_authenticated:
        is_registered = EventRegistration.objects.filter(event=event, user=request.user).exists()

    participants = EventRegistration.objects.filter(event=event).select_related('user').order_by('-registered_at')

    is_manager = False
    if request.user.is_authenticated:
        is_manager = (
            request.user == event.organizer or
            request.user.is_staff or
            request.user.is_superuser
        )

    return render(request, 'event_detail.html', {
        'event': event,
        'is_registered': is_registered,
        'participants': participants,
        'is_manager': is_manager,
    })


def event_register_toggle_api(request, event_id):
    """
    API đăng ký / hủy đăng ký tham gia sự kiện tương tác realtime (AJAX):
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Vui lòng đăng nhập để đăng ký tham gia sự kiện!'}, status=401)

    event = get_object_or_404(Event, id=event_id)

    if event.is_past or event.status in [Event.STATUS_COMPLETED, Event.STATUS_CANCELLED]:
        return JsonResponse({'success': False, 'message': 'Sự kiện đã kết thúc hoặc bị hủy, không thể thay đổi đăng ký.'})

    reg = EventRegistration.objects.filter(event=event, user=request.user).first()
    if reg:
        # Hủy đăng ký
        reg.delete()
        registered = False
        msg = f"Đã hủy đăng ký sự kiện '{event.title}' thành công."
    else:
        # Đăng ký mới
        if event.is_full:
            return JsonResponse({'success': False, 'message': 'Rất tiếc, sự kiện đã đủ số lượng người đăng ký tối đa!'})
        EventRegistration.objects.create(event=event, user=request.user)
        registered = True
        msg = f"Chúc mừng bạn đã đăng ký tham gia thành công sự kiện '{event.title}'!"

    return JsonResponse({
        'success': True,
        'registered': registered,
        'message': msg,
        'total_registered': event.registrations.count(),
        'available_slots': event.available_slots,
        'is_full': event.is_full,
    })


def event_create(request):
    """
    Tạo sự kiện nội bộ mới (dành cho Trainer / Quản lý / Admin):
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=/events/create/')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', Event.CATEGORY_TRAINING)
        description = request.POST.get('description', '').strip()
        agenda = request.POST.get('agenda', '').strip()
        date_start = request.POST.get('date_start')
        date_end = request.POST.get('date_end')
        location = request.POST.get('location', '').strip()
        branch_id = request.POST.get('branch')
        department_id = request.POST.get('department')
        max_participants = int(request.POST.get('max_participants', 50) or 50)
        banner = request.FILES.get('banner')

        if not title or not date_start or not date_end or not location:
            messages.error(request, 'Vui lòng điền đầy đủ các thông tin bắt buộc (*).')
        else:
            branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
            department = Department.objects.filter(id=department_id).first() if department_id else None

            ev = Event.objects.create(
                title=title,
                category=category,
                description=description,
                agenda=agenda,
                date_start=date_start,
                date_end=date_end,
                location=location,
                branch=branch,
                department=department,
                organizer=request.user,
                max_participants=max_participants,
                banner=banner,
                status=Event.STATUS_UPCOMING,
            )
            messages.success(request, f'Sự kiện "{ev.title}" đã được tạo thành công!')
            return redirect('event_detail', event_id=ev.id)

    branches = Branch.objects.all().order_by('name')
    departments = Department.objects.all().order_by('name')

    return render(request, 'event_form.html', {
        'branches': branches,
        'departments': departments,
        'category_choices': Event.CATEGORY_CHOICES,
        'is_edit': False,
    })


def event_edit(request, event_id):
    """
    Chỉnh sửa thông tin sự kiện:
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)

    event = get_object_or_404(Event, id=event_id)

    if not (request.user == event.organizer or request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Bạn không có quyền chỉnh sửa sự kiện này.')
        return redirect('event_detail', event_id=event.id)

    if request.method == 'POST':
        event.title = request.POST.get('title', event.title).strip()
        event.category = request.POST.get('category', event.category)
        event.description = request.POST.get('description', event.description).strip()
        event.agenda = request.POST.get('agenda', event.agenda).strip()
        
        date_start = request.POST.get('date_start')
        date_end = request.POST.get('date_end')
        if date_start:
            event.date_start = date_start
        if date_end:
            event.date_end = date_end

        event.location = request.POST.get('location', event.location).strip()
        branch_id = request.POST.get('branch')
        event.branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
        
        department_id = request.POST.get('department')
        event.department = Department.objects.filter(id=department_id).first() if department_id else None

        event.max_participants = int(request.POST.get('max_participants', event.max_participants) or 50)
        event.status = request.POST.get('status', event.status)
        
        if request.FILES.get('banner'):
            event.banner = request.FILES.get('banner')

        event.save()
        messages.success(request, f'Đã cập nhật sự kiện "{event.title}" thành công!')
        return redirect('event_detail', event_id=event.id)

    branches = Branch.objects.all().order_by('name')
    departments = Department.objects.all().order_by('name')

    return render(request, 'event_form.html', {
        'event': event,
        'branches': branches,
        'departments': departments,
        'category_choices': Event.CATEGORY_CHOICES,
        'status_choices': Event.STATUS_CHOICES,
        'is_edit': True,
    })


def event_delete(request, event_id):
    """
    Xóa sự kiện:
    """
    if not request.user.is_authenticated:
        return redirect('login')

    event = get_object_or_404(Event, id=event_id)

    if not (request.user == event.organizer or request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Bạn không có quyền xóa sự kiện này.')
        return redirect('event_detail', event_id=event.id)

    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f'Đã xóa sự kiện "{title}" thành công.')
        return redirect('events_list')

    return render(request, 'event_confirm_delete.html', {'event': event})

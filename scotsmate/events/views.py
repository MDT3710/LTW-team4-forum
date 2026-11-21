from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from home.models import Branch, Department
from home.roles import (
    is_department_manager,
    is_it_admin,
    redirect_back_with_error,
)
from .forms import EventForm
from .models import Event, EventRegistration


def _can_manage_events(user):
    """Chỉ Trưởng phòng và Admin mới có quyền tạo, chỉnh sửa, xóa sự kiện."""
    return bool(user and user.is_authenticated and (is_department_manager(user) or is_it_admin(user)))


@login_required
def events_list(request):
    """
    Trang danh sách sự kiện toàn hệ thống Scots English:
    - Tìm kiếm theo từ khóa (tiêu đề, địa điểm, mô tả).
    - Lọc theo phân loại, chi nhánh.
    - Phân tab đồng bộ số đếm: 'all', 'upcoming', 'my', 'past'.
    """
    tab = request.GET.get('tab', 'all')
    category = request.GET.get('category', '')
    branch_id = request.GET.get('branch', '')
    query = request.GET.get('q', '').strip()

    now = timezone.now()
    upcoming_q = Q(date_end__gte=now) & ~Q(status__in=[Event.STATUS_COMPLETED, Event.STATUS_CANCELLED])
    past_q = Q(date_end__lt=now) | Q(status=Event.STATUS_COMPLETED)

    events_qs = Event.objects.select_related('organizer', 'branch', 'department').prefetch_related('registrations')

    if tab == 'upcoming':
        events_qs = events_qs.filter(upcoming_q)
    elif tab == 'my':
        events_qs = events_qs.filter(registrations__user=request.user).distinct()
    elif tab == 'past':
        events_qs = events_qs.filter(past_q)

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

    user_registered_event_ids = set(
        EventRegistration.objects.filter(user=request.user).values_list('event_id', flat=True)
    )

    events = list(events_qs.order_by('-date_start'))
    for ev in events:
        ev.is_user_registered = ev.id in user_registered_event_ids

    branches = Branch.objects.all().order_by('name')

    counts = {
        'all': Event.objects.count(),
        'upcoming': Event.objects.filter(upcoming_q).count(),
        'my': EventRegistration.objects.filter(user=request.user).values('event_id').distinct().count(),
        'past': Event.objects.filter(past_q).count(),
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


@login_required
def event_detail(request, event_id):
    """
    Trang chi tiết sự kiện:
    - Thông tin chi tiết, lịch trình (Agenda), danh sách người tham dự.
    - Đăng ký / Hủy đăng ký (chỉ trước thời điểm bắt đầu).
    - Nút Chỉnh sửa / Xóa dành riêng cho Trưởng phòng và Admin.
    """
    event = get_object_or_404(
        Event.objects.select_related('organizer', 'branch', 'department'),
        id=event_id
    )

    is_registered = EventRegistration.objects.filter(event=event, user=request.user).exists()
    participants = EventRegistration.objects.filter(event=event).select_related('user').order_by('-registered_at')
    is_manager = _can_manage_events(request.user)

    return render(request, 'event_detail.html', {
        'event': event,
        'is_registered': is_registered,
        'participants': participants,
        'is_manager': is_manager,
    })


def event_register_toggle_api(request, event_id):
    """
    API đăng ký / hủy đăng ký tham gia sự kiện (chỉ chấp nhận POST, chỉ trước khi sự kiện bắt đầu).
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Vui lòng đăng nhập để đăng ký tham gia sự kiện!'}, status=401)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Phương thức không được hỗ trợ.'}, status=405)

    with transaction.atomic():
        event = get_object_or_404(Event.objects.select_for_update(), id=event_id)

        if not event.can_register:
            return JsonResponse({
                'success': False,
                'message': 'Chỉ được phép đăng ký hoặc hủy đăng ký trước khi sự kiện bắt đầu.'
            }, status=400)

        reg = EventRegistration.objects.filter(event=event, user=request.user).first()
        if reg:
            reg.delete()
            registered = False
            msg = f"Đã hủy đăng ký sự kiện '{event.title}' thành công."
        else:
            total_reg = EventRegistration.objects.filter(event=event).count()
            if total_reg >= event.max_participants:
                return JsonResponse({
                    'success': False,
                    'message': 'Rất tiếc, sự kiện đã đủ số lượng người đăng ký tối đa!'
                }, status=400)
            EventRegistration.objects.create(event=event, user=request.user)
            registered = True
            msg = f"Chúc mừng bạn đã đăng ký tham gia thành công sự kiện '{event.title}'!"

        total_registered = EventRegistration.objects.filter(event=event).count()
        available_slots = max(0, event.max_participants - total_registered)
        is_full = total_registered >= event.max_participants
        my_events_count = EventRegistration.objects.filter(user=request.user).values('event_id').distinct().count()

    return JsonResponse({
        'success': True,
        'registered': registered,
        'message': msg,
        'total_registered': total_registered,
        'max_participants': event.max_participants,
        'available_slots': available_slots,
        'is_full': is_full,
        'my_events_count': my_events_count,
    })


@login_required
def event_create(request):
    """Tạo sự kiện nội bộ mới (chỉ Trưởng phòng hoặc Admin)."""
    if not _can_manage_events(request.user):
        return redirect_back_with_error(
            request,
            'Chỉ Trưởng phòng hoặc Admin mới có quyền tạo sự kiện nội bộ.',
            fallback_url='events_list',
        )

    if request.method == 'POST':
        form = EventForm(request.POST, is_edit=False)
        if form.is_valid():
            ev = form.save(commit=False)
            ev.organizer = request.user
            ev.status = Event.STATUS_UPCOMING
            ev.save()
            messages.success(request, f'Sự kiện "{ev.title}" đã được tạo thành công!')
            return redirect('event_detail', event_id=ev.id)
        for errs in form.errors.values():
            messages.error(request, errs[0])
    else:
        form = EventForm(is_edit=False)

    branches = Branch.objects.all().order_by('name')
    departments = Department.objects.all().order_by('name')

    return render(request, 'event_form.html', {
        'form': form,
        'form_values': request.POST if request.method == 'POST' else None,
        'branches': branches,
        'departments': departments,
        'category_choices': Event.CATEGORY_CHOICES,
        'is_edit': False,
    })


@login_required
def event_edit(request, event_id):
    """Chỉnh sửa sự kiện (chỉ Trưởng phòng hoặc Admin)."""
    event = get_object_or_404(Event, id=event_id)

    if not _can_manage_events(request.user):
        return redirect_back_with_error(
            request,
            'Chỉ Trưởng phòng hoặc Admin mới có quyền chỉnh sửa sự kiện.',
            fallback_url='events_list',
        )

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event, is_edit=True)
        if form.is_valid():
            ev = form.save()
            messages.success(request, f'Đã cập nhật sự kiện "{ev.title}" thành công!')
            return redirect('event_detail', event_id=ev.id)
        for errs in form.errors.values():
            messages.error(request, errs[0])
    else:
        form = EventForm(instance=event, is_edit=True)

    branches = Branch.objects.all().order_by('name')
    departments = Department.objects.all().order_by('name')

    return render(request, 'event_form.html', {
        'event': event,
        'form': form,
        'form_values': request.POST if request.method == 'POST' else None,
        'branches': branches,
        'departments': departments,
        'category_choices': Event.CATEGORY_CHOICES,
        'status_choices': Event.STATUS_CHOICES,
        'is_edit': True,
    })


@login_required
def event_delete(request, event_id):
    """Xóa sự kiện (chỉ Trưởng phòng hoặc Admin)."""
    event = get_object_or_404(Event, id=event_id)

    if not _can_manage_events(request.user):
        return redirect_back_with_error(
            request,
            'Chỉ Trưởng phòng hoặc Admin mới có quyền xóa sự kiện.',
            fallback_url='events_list',
        )

    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f'Đã xóa sự kiện "{title}" thành công.')
        return redirect('events_list')

    return render(request, 'event_confirm_delete.html', {'event': event})

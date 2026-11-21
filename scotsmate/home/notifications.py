import logging
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def _format_time_label(dt):
    if not dt:
        return 'Gần đây'
    if hasattr(dt, 'utcoffset') and dt.utcoffset() is not None:
        return timezone.localtime(dt).strftime('%H:%M %d/%m')
    return dt.strftime('%d/%m/%Y')


def get_user_notifications(request):
    """
    Tổng hợp thông báo thật theo người dùng hiện tại từ các module:
    Tin nhắn, Đào tạo, Tài liệu, Khảo sát và Sự kiện.
    Trạng thái đã đọc được lưu theo session (`read_notification_ids`).
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return [], 0

    from courses.models import CourseEnrollment
    from documents.models import Document
    from events.models import Event
    from home.roles import is_department_manager, is_it_admin
    from message.models import Conversation, ConversationMember, Message
    from surveys.models import Survey

    now = timezone.now()
    session = getattr(request, 'session', None)
    read_ids = set(session.get('read_notification_ids', [])) if session is not None else set()

    emp_info = getattr(user, 'employee_info', None)
    user_dep = getattr(emp_info, 'dep', None) if emp_info else None
    admin_flag = is_it_admin(user)
    manager_flag = is_department_manager(user)

    items = []

    try:
        # 1. Tin nhắn mới chưa đọc
        memberships = {
            cm.conversation_id: cm.last_read_at
            for cm in ConversationMember.objects.filter(user=user).only('conversation_id', 'last_read_at')
        }
        if memberships:
            recent_msgs = (
                Message.objects.filter(conversation_id__in=memberships.keys())
                .exclude(sender=user)
                .select_related('conversation', 'sender')
                .order_by('-created_at')[:10]
            )
            seen_convs = set()
            for msg in recent_msgs:
                if msg.conversation_id in seen_convs:
                    continue
                last_read = memberships.get(msg.conversation_id)
                if last_read and msg.created_at <= last_read:
                    continue
                seen_convs.add(msg.conversation_id)
                conv = msg.conversation
                if conv.conversation_type == Conversation.TYPE_GROUP:
                    url = f'/message/group/{conv.id}/'
                else:
                    url = f'/message/inbox/{msg.sender_id}/'
                sender_name = msg.sender.get_full_name() or msg.sender.username
                snippet = (msg.content or '[Tệp đính kèm]').strip()[:55]
                items.append({
                    'id': f'msg-{msg.id}',
                    'category': 'message',
                    'title': 'Tin nhắn mới:',
                    'body': f'{sender_name}: {snippet}',
                    'meta': f'{_format_time_label(msg.created_at)} • Messenger',
                    'url': url,
                })
                if len(seen_convs) >= 2:
                    break

        # 2. Tài liệu chờ duyệt (dành cho Trưởng phòng / Admin)
        if admin_flag or manager_flag:
            pending_docs = Document.objects.filter(status='PENDING').count()
            if pending_docs > 0:
                items.append({
                    'id': f'doc-pending-{pending_docs}',
                    'category': 'document',
                    'title': 'Tài liệu chờ duyệt:',
                    'body': f'Hiện có {pending_docs} tài liệu đang chờ phê duyệt.',
                    'meta': 'Cần xử lý • Thư viện Tài liệu',
                    'url': '/documents/approve/',
                })

        # 3. Khóa học đang tham gia chưa hoàn thành
        enrollments = (
            CourseEnrollment.objects.filter(
                emp=user,
                is_completed=False,
                course__status='ongoing',
            )
            .select_related('course')
            .order_by('-enrollment_date')[:2]
        )
        for en in enrollments:
            items.append({
                'id': f'course-{en.course_id}',
                'category': 'course',
                'title': 'Khóa học đang tham gia:',
                'body': en.course.title,
                'meta': 'Đang triển khai • Cổng Đào tạo',
                'url': f'/courses/trainee/courses/{en.course_id}/',
            })

        # 4. Khảo sát đang mở chưa hoàn thành
        surveys_qs = (
            Survey.objects.filter(is_approved=True, is_visible=True, is_respondable=True)
            .filter(Q(response_deadline__isnull=True) | Q(response_deadline__gte=now))
            .exclude(responses__respondent=user, responses__submission_date__isnull=False)
        )
        if not admin_flag:
            access_filter = Q(access_permissions__emp=user, access_permissions__can_respond=True)
            if user_dep is not None:
                access_filter |= Q(department=user_dep)
            surveys_qs = surveys_qs.filter(access_filter).distinct()
        for sv in surveys_qs.order_by('-date_created')[:2]:
            items.append({
                'id': f'survey-{sv.id}',
                'category': 'survey',
                'title': 'Khảo sát:',
                'body': sv.name,
                'meta': f'{sv.time_left or "Đang mở"} • Khảo sát',
                'url': f'/surveys/{sv.id}/',
            })

        # 5. Tài liệu mới ban hành
        docs_qs = Document.objects.filter(status='APPROVED', is_visible=True)
        if not admin_flag:
            doc_scope = Q(access_scope='ALL')
            if user_dep is not None:
                doc_scope |= Q(access_permissions__department=user_dep)
            docs_qs = docs_qs.filter(doc_scope).distinct()
        for doc in docs_qs.order_by('-approved_at', '-updated_at')[:1]:
            items.append({
                'id': f'doc-{doc.id}',
                'category': 'document',
                'title': 'Tài liệu mới:',
                'body': doc.title,
                'meta': f'{_format_time_label(doc.approved_at or doc.updated_at)} • Thư viện Tài liệu',
                'url': f'/documents/{doc.category_id}/',
            })

        # 6. Sự kiện sắp tới
        for ev in Event.objects.filter(status=Event.STATUS_UPCOMING, date_start__gte=now).order_by('date_start')[:2]:
            items.append({
                'id': f'event-{ev.id}',
                'category': 'event',
                'title': 'Sự kiện sắp tới:',
                'body': ev.title,
                'meta': f'{_format_time_label(ev.date_start)} • Sự kiện',
                'url': f'/events/{ev.id}/',
            })
    except Exception as exc:
        logger.warning('Failed to build user notifications: %s', exc)

    items = items[:8]
    unread_count = 0
    for item in items:
        item['is_unread'] = item['id'] not in read_ids
        if item['is_unread']:
            unread_count += 1

    return items, unread_count

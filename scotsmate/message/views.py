import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Attachment, Conversation, ConversationMember, Message, StaffProfile
from home.models import Branch
from home.roles import get_primary_role_label, is_department_manager, is_it_admin, redirect_back_with_error

MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20 MB

try:
    from posts.colleagues import COLLEAGUES_DATA
except ImportError:
    COLLEAGUES_DATA = {}


DEFAULT_AVATAR_PALETTE = (
    'bg-blue-100 text-[#134c81]',
    'bg-emerald-100 text-emerald-800',
    'bg-purple-100 text-purple-800',
    'bg-amber-100 text-amber-800',
    'bg-blue-50 text-blue-700',
)


def _can_create_group(user):
    return is_it_admin(user) or is_department_manager(user)


def _can_manage_group(user, group):
    if not user or not user.is_authenticated:
        return False
    if is_it_admin(user):
        return True
    return ConversationMember.objects.filter(
        conversation=group, user=user, role=ConversationMember.ROLE_ADMIN
    ).exists()


def _get_branch_choices():
    """Lấy danh sách chi nhánh động từ bảng Branch (kèm StaffProfile nếu có)."""
    names = list(Branch.objects.order_by('name').values_list('name', flat=True))
    extra = [
        b for b in StaffProfile.objects.exclude(branch='').values_list('branch', flat=True).distinct()
        if b and b not in names
    ]
    combined = names + sorted(extra)
    return combined or ['Chi nhánh Cầu Giấy', 'Chi nhánh Hà Đông', 'Chi nhánh Đống Đa']


def _mark_conversation_read(convo, user):
    """Đánh dấu đã xem tin nhắn của người khác và cập nhật last_read_at cho thành viên."""
    if not convo or not user or not user.is_authenticated:
        return
    Message.objects.filter(conversation=convo, is_read=False).exclude(sender=user).update(is_read=True)
    ConversationMember.objects.filter(conversation=convo, user=user).update(last_read_at=timezone.now())


def _compute_initials(text, fallback='SC'):
    """Tính 2 chữ cái viết tắt hiển thị trong avatar tròn từ tên hoặc tiêu đề."""
    cleaned = (text or '').strip()
    if not cleaned:
        return fallback
    parts = cleaned.split()
    if len(parts) >= 2:
        return f"{parts[-2][0]}{parts[-1][0]}".upper()
    return cleaned[:2].upper()


def get_current_user(request):
    """Trả về user đang đăng nhập (không fallback ẩn danh)."""
    return request.user if getattr(request, 'user', None) and request.user.is_authenticated else None


def _get_user_display_info(user):
    """Trả về tên hiển thị, chữ viết tắt avatar, màu nền và chức danh của user."""
    if not user:
        return {
            'display_name': 'Người dùng',
            'initials': 'SC',
            'position': 'Nhân viên',
            'branch': 'Chi nhánh Cầu Giấy',
            'avatar_color': 'bg-blue-100 text-[#134c81]',
        }

    profile = getattr(user, 'profile', None)
    emp_info = getattr(user, 'employee_info', None)
    colleague_meta = COLLEAGUES_DATA.get(getattr(user, 'username', ''), {})
    full_name = (user.get_full_name() or '').strip()

    if full_name:
        display_name = full_name
    elif colleague_meta.get('name'):
        display_name = colleague_meta['name']
    elif getattr(user, 'username', '').lower() == 'admin' or user.is_superuser:
        display_name = 'Quản trị viên hệ thống'
    else:
        display_name = user.username

    if is_it_admin(user):
        default_role = 'Admin (Phòng IT)'
    else:
        default_role = get_primary_role_label(user) or colleague_meta.get('job_title') or 'Nhân viên'

    emp_branch_name = emp_info.branch.name if (emp_info and getattr(emp_info, 'branch', None)) else ''
    default_branch = emp_branch_name or colleague_meta.get('branch') or 'Chi nhánh Cầu Giấy'
    default_color = DEFAULT_AVATAR_PALETTE[(user.id or 0) % len(DEFAULT_AVATAR_PALETTE)]

    if profile:
        initials = profile.get_initials() if full_name else _compute_initials(display_name)
        position = profile.position or profile.department or default_role
        branch = emp_branch_name or profile.branch or default_branch
        avatar_color = profile.avatar_color or default_color
    else:
        initials = _compute_initials(display_name)
        position = default_role
        branch = default_branch
        avatar_color = default_color

    return {
        'display_name': display_name,
        'initials': initials,
        'position': position,
        'branch': branch,
        'avatar_color': avatar_color,
    }


def _resolve_direct_conversation_display(convo, target_user):
    """Lấy tên & chữ viết tắt hiển thị thực tế của đối phương cho chat 1-1."""
    target_info = _get_user_display_info(target_user)
    return target_info['display_name'], target_info['initials'], target_info


def get_sidebar_conversations(user):
    """Lấy danh sách cuộc trò chuyện cho cột Hộp thư, sắp xếp theo -updated_at."""
    if not user or not user.is_authenticated:
        return []

    if is_it_admin(user):
        qs = Conversation.objects.filter(
            Q(members=user) | Q(conversation_type=Conversation.TYPE_GROUP)
        ).order_by('-updated_at')
    else:
        qs = Conversation.objects.filter(members=user).order_by('-updated_at')
    viewer = user

    raw_conversations = list(
        qs.distinct().prefetch_related('members__profile', 'members__employee_info__branch', 'memberships', 'messages')
    )

    conversations = []
    for convo in raw_conversations:
        members_list = list(convo.members.all())
        memberships_list = list(convo.memberships.all())
        messages_list = list(convo.messages.all())
        convo.member_count = len(members_list)
        convo.last_msg = messages_list[-1] if messages_list else None
        viewer_ms = next((m for m in memberships_list if m.user_id == viewer.id), None)
        convo.is_muted = bool(viewer_ms and viewer_ms.is_muted)

        if viewer_ms:
            last_read = viewer_ms.last_read_at
            convo.unread_count = sum(
                1 for m in messages_list
                if m.sender_id != viewer.id and (last_read is None or m.created_at > last_read)
            )
        else:
            convo.unread_count = 0

        if convo.conversation_type == Conversation.TYPE_GROUP:
            convo.display_name = convo.title or f"Nhóm #{convo.id}"
            convo.display_initials = convo.get_initials()
            convo.target_user_id = None
            conversations.append(convo)
        else:
            other_user = next((m for m in members_list if m.id != viewer.id), None)
            if other_user is None:
                continue

            display_name, display_initials, _ = _resolve_direct_conversation_display(convo, other_user)
            convo.display_name = display_name
            convo.display_initials = display_initials
            convo.target_user_id = other_user.id
            conversations.append(convo)

    return conversations


def _handle_message_post(request, conversation, sender):
    """Lưu tin nhắn và file đính kèm (nếu có), đồng thời cập nhật updated_at."""
    if not sender or not sender.is_authenticated:
        return False

    content = (request.POST.get('content') or '').strip()
    attachment = request.FILES.get('attachment')
    if attachment and attachment.size > MAX_ATTACHMENT_BYTES:
        messages.error(request, 'Tệp đính kèm vượt quá giới hạn tối đa 20 MB.')
        return False

    if content or attachment:
        ConversationMember.objects.get_or_create(
            conversation=conversation,
            user=sender,
            defaults={'role': ConversationMember.ROLE_MEMBER}
        )
        new_message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content,
        )
        if attachment:
            Attachment.objects.create(
                message=new_message,
                file=attachment,
                file_name=attachment.name,
            )
        _mark_conversation_read(conversation, sender)
        conversation.save()
        return True
    return False


def _initialize_auto_group(group, creator):
    """Thêm người tạo và tin nhắn chào mừng mẫu khi tự khởi tạo nhóm mặc định."""
    ConversationMember.objects.get_or_create(
        conversation=group,
        user=creator,
        defaults={'role': ConversationMember.ROLE_ADMIN},
    )
    Message.objects.create(
        conversation=group,
        sender=creator,
        content=f"Chào mừng mọi người đến với {group.title}!",
    )


def _get_or_create_direct_conversation(current_user, target_user):
    """Tìm cuộc trò chuyện trực tiếp 1-1 giữa 2 người; nếu chưa có thì tạo mới."""
    candidates = (
        Conversation.objects.filter(
            conversation_type=Conversation.TYPE_DIRECT,
            members=current_user,
        )
        .filter(members=target_user)
        .distinct()
        .prefetch_related('members')
    )
    expected_member_ids = {current_user.id, target_user.id}
    conversation = next(
        (c for c in candidates if {m.id for m in c.members.all()} == expected_member_ids),
        None,
    )

    if conversation is None:
        conversation = Conversation.objects.create(
            conversation_type=Conversation.TYPE_DIRECT,
            created_by=current_user,
        )
        ConversationMember.objects.get_or_create(
            conversation=conversation,
            user=current_user,
        )
        if target_user.id != current_user.id:
            ConversationMember.objects.get_or_create(
                conversation=conversation,
                user=target_user,
            )

    return conversation


def _redirect_to_conversation(conversation, current_user):
    """Điều hướng về đúng màn hình chi tiết của nhóm hoặc chat 1-1."""
    if conversation.conversation_type == Conversation.TYPE_GROUP:
        return redirect('group_detail', group_id=conversation.id)
    other_user = conversation.get_other_user(current_user) or current_user
    return redirect('inbox_detail', user_id=other_user.id)


def _get_conversation_sidebar_extras(conversation, current_user):
    """Lấy trạng thái tắt thông báo và danh sách file phương tiện / tài liệu của hội thoại."""
    membership = (
        ConversationMember.objects.filter(
            conversation=conversation,
            user=current_user,
        ).first()
        if current_user
        else None
    )
    attachments = list(
        Attachment.objects.filter(message__conversation=conversation)
        .select_related('message__sender')
        .order_by('-created_at')
    )
    media_files = [a for a in attachments if a.attachment_type == Attachment.TYPE_MEDIA]
    document_files = [a for a in attachments if a.attachment_type == Attachment.TYPE_DOCUMENT]
    return {
        'is_muted': bool(membership and membership.is_muted),
        'media_files': media_files,
        'document_files': document_files,
    }


def _annotate_messages_for_display(messages_qs):
    """Gắn sẵn tên hiển thị thực tế cho người gửi từng tin nhắn."""
    messages = list(messages_qs)
    for msg in messages:
        msg.sender_display_name = _get_user_display_info(msg.sender)['display_name']
    return messages


def _branch_matches(branch_filter, display_branch):
    """Khớp mềm tên chi nhánh (ví dụ: 'Chi nhánh Cầu Giấy' với 'Cầu Giấy, Hà Nội')."""
    short = branch_filter.replace('Chi nhánh ', '').strip().lower()
    return short in (display_branch or '').lower()


def _get_colleague_users(current_user, query='', branch=''):
    """Lấy danh sách nhân sự đang hoạt động (loại trừ current_user), hỗ trợ lọc."""
    users_qs = (
        User.objects.filter(is_active=True)
        .exclude(id=current_user.id)
        .exclude(is_superuser=True, first_name='', last_name='')
        .select_related('profile', 'employee_info__branch', 'employee_info__dep')
        .order_by('id')
    )

    if query:
        users_qs = users_qs.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
            | Q(email__icontains=query)
        )

    users = []
    for u in users_qs:
        info = _get_user_display_info(u)
        if branch and branch != 'ALL':
            user_branch = (info.get('branch') or '').strip()
            if user_branch != branch and not _branch_matches(branch, user_branch):
                continue
        u.display_info = info
        users.append(u)
    return users


@login_required
def messages_list(request):
    current_user = request.user
    conversations = get_sidebar_conversations(current_user)
    return render(request, 'messages.html', {
        'conversations': conversations,
        'current_user': current_user,
    })


@login_required
def group_detail(request, group_id=1):
    current_user = request.user
    current_group = Conversation.objects.filter(
        id=group_id,
        conversation_type=Conversation.TYPE_GROUP,
    ).first()

    if current_group is None:
        return redirect_back_with_error(
            request,
            'Nhóm trò chuyện không tồn tại hoặc đã bị xóa.',
            fallback_url='messages_list',
        )

    is_member = current_group.members.filter(id=current_user.id).exists()
    if not is_member and not is_it_admin(current_user):
        return redirect_back_with_error(
            request,
            'Bạn không phải thành viên của nhóm chat này.',
            fallback_url='messages_list',
        )

    if request.method == 'POST':
        _handle_message_post(request, current_group, current_user)
        return redirect('group_detail', group_id=group_id)

    _mark_conversation_read(current_group, current_user)
    conversations = get_sidebar_conversations(current_user)
    messages_list_qs = _annotate_messages_for_display(
        current_group.messages.all()
        .select_related('sender', 'sender__profile', 'sender__employee_info__branch')
        .prefetch_related('attachments')
    )
    memberships = list(
        ConversationMember.objects.filter(conversation=current_group)
        .select_related('user', 'user__profile', 'user__employee_info__branch')
        .order_by('-role', 'joined_at')
    )
    members = []
    admin_names = []
    member_ids = set()
    for ms in memberships:
        u = ms.user
        u.display_info = _get_user_display_info(u)
        u.is_group_admin = (ms.role == ConversationMember.ROLE_ADMIN)
        members.append(u)
        member_ids.add(u.id)
        if u.is_group_admin:
            admin_names.append(u.display_info['display_name'])

    if admin_names:
        admin_name = ', '.join(admin_names)
    elif current_group.created_by:
        admin_name = _get_user_display_info(current_group.created_by)['display_name']
    else:
        admin_name = 'Chưa cập nhật'

    can_manage_group = _can_manage_group(current_user, current_group)
    available_users_to_add = [
        u for u in _get_colleague_users(current_user) if u.id not in member_ids
    ] if can_manage_group else []
    extras = _get_conversation_sidebar_extras(current_group, current_user)

    return render(request, 'group.html', {
        'group_id': group_id,
        'conversations': conversations,
        'current_group': current_group,
        'active_convo': None,
        'current_user': current_user,
        'messages': messages_list_qs,
        'flash_messages': list(messages.get_messages(request)),
        'members': members,
        'admin_name': admin_name,
        'can_manage_group': can_manage_group,
        'is_member': is_member,
        'available_users_to_add': available_users_to_add,
        **extras,
    })


@login_required
def group_leave(request, group_id):
    """Cho phép thành viên (Nhân viên/Trưởng phòng/Admin) rời khỏi nhóm chat."""
    current_user = request.user
    group = get_object_or_404(Conversation, id=group_id, conversation_type=Conversation.TYPE_GROUP)
    if request.method != 'POST':
        return redirect('group_detail', group_id=group.id)

    membership = ConversationMember.objects.filter(conversation=group, user=current_user).first()
    if not membership:
        return redirect_back_with_error(request, 'Bạn không phải thành viên của nhóm này.', fallback_url='messages_list')

    was_admin = (membership.role == ConversationMember.ROLE_ADMIN)
    membership.delete()

    remaining = ConversationMember.objects.filter(conversation=group).order_by('joined_at')
    if not remaining.exists():
        group.delete()
    elif was_admin and not remaining.filter(role=ConversationMember.ROLE_ADMIN).exists():
        next_admin = remaining.first()
        next_admin.role = ConversationMember.ROLE_ADMIN
        next_admin.save(update_fields=['role'])

    messages.success(request, f'Bạn đã rời khỏi nhóm "{group.title}".')
    return redirect('messages_list')


@login_required
def group_add_member(request, group_id):
    """Thêm thành viên vào nhóm chat (Chỉ Quản trị viên nhóm / Admin hệ thống)."""
    current_user = request.user
    group = get_object_or_404(Conversation, id=group_id, conversation_type=Conversation.TYPE_GROUP)
    if not _can_manage_group(current_user, group):
        return redirect_back_with_error(
            request,
            'Chỉ Quản trị viên nhóm hoặc Admin mới có quyền thêm thành viên.',
            fallback_url='messages_list',
        )
    if request.method == 'POST':
        user_id = request.POST.get('user_id', '').strip()
        if user_id.isdigit():
            target_user = get_object_or_404(User, id=int(user_id), is_active=True)
            _, created = ConversationMember.objects.get_or_create(
                conversation=group,
                user=target_user,
                defaults={'role': ConversationMember.ROLE_MEMBER},
            )
            target_name = _get_user_display_info(target_user)['display_name']
            if created:
                messages.success(request, f'Đã thêm {target_name} vào nhóm.')
            else:
                messages.info(request, f'{target_name} đã ở trong nhóm.')
    return redirect('group_detail', group_id=group.id)


@login_required
def group_remove_member(request, group_id, user_id):
    """Xóa thành viên khỏi nhóm chat (Chỉ QTV nhóm / Admin hệ thống; không xóa người tạo nhóm)."""
    current_user = request.user
    group = get_object_or_404(Conversation, id=group_id, conversation_type=Conversation.TYPE_GROUP)
    if not _can_manage_group(current_user, group):
        return redirect_back_with_error(
            request,
            'Chỉ Quản trị viên nhóm hoặc Admin mới có quyền xóa thành viên.',
            fallback_url='messages_list',
        )
    if request.method == 'POST':
        if user_id == current_user.id:
            return redirect_back_with_error(
                request,
                'Hãy dùng nút "Rời nhóm chat" nếu bạn muốn rời nhóm.',
                fallback_url=f'/message/group/{group.id}/',
            )
        if group.created_by_id and user_id == group.created_by_id:
            return redirect_back_with_error(
                request,
                'Không thể xóa người tạo nhóm khỏi nhóm chat.',
                fallback_url=f'/message/group/{group.id}/',
            )
        target_ms = ConversationMember.objects.filter(conversation=group, user_id=user_id).select_related('user').first()
        if target_ms:
            was_admin = (target_ms.role == ConversationMember.ROLE_ADMIN)
            target_name = _get_user_display_info(target_ms.user)['display_name']
            target_ms.delete()
            if was_admin:
                remaining = ConversationMember.objects.filter(conversation=group).order_by('joined_at')
                if remaining.exists() and not remaining.filter(role=ConversationMember.ROLE_ADMIN).exists():
                    next_admin = remaining.first()
                    next_admin.role = ConversationMember.ROLE_ADMIN
                    next_admin.save(update_fields=['role'])
            messages.success(request, f'Đã xóa {target_name} khỏi nhóm.')
    return redirect('group_detail', group_id=group.id)


@login_required
def group_grant_admin(request, group_id, user_id):
    """Trao quyền quản trị viên nhóm chat cho thành viên (Chỉ QTV nhóm / Admin hệ thống)."""
    current_user = request.user
    group = get_object_or_404(Conversation, id=group_id, conversation_type=Conversation.TYPE_GROUP)
    if not _can_manage_group(current_user, group):
        return redirect_back_with_error(
            request,
            'Chỉ Quản trị viên nhóm hoặc Admin mới có quyền trao quyền quản trị viên.',
            fallback_url='messages_list',
        )
    if request.method == 'POST':
        target_ms = get_object_or_404(ConversationMember, conversation=group, user_id=user_id)
        target_ms.role = ConversationMember.ROLE_ADMIN
        target_ms.save(update_fields=['role'])
        target_name = _get_user_display_info(target_ms.user)['display_name']
        messages.success(request, f'Đã trao quyền quản trị viên nhóm cho {target_name}.')
    return redirect('group_detail', group_id=group.id)


@login_required
def group_delete(request, group_id):
    """Xóa nhóm chat (Chỉ QTV nhóm / Admin hệ thống)."""
    current_user = request.user
    group = get_object_or_404(Conversation, id=group_id, conversation_type=Conversation.TYPE_GROUP)
    if not _can_manage_group(current_user, group):
        return redirect_back_with_error(
            request,
            'Chỉ Quản trị viên nhóm hoặc Admin mới có quyền xóa nhóm chat.',
            fallback_url='messages_list',
        )
    if request.method == 'POST':
        title = group.title or f'Nhóm #{group.id}'
        group.delete()
        messages.success(request, f'Đã xóa nhóm chat "{title}".')
        return redirect('messages_list')
    return redirect('group_detail', group_id=group.id)


@login_required
def inbox_detail(request, user_id=1):
    current_user = request.user
    target_user = get_object_or_404(User, id=user_id, is_active=True)
    if target_user.id == current_user.id:
        return redirect_back_with_error(
            request,
            'Không thể tự nhắn tin với chính mình.',
            fallback_url='messages_list',
        )

    convo = _get_or_create_direct_conversation(current_user, target_user)

    if request.method == 'POST':
        _handle_message_post(request, convo, current_user)
        return redirect('inbox_detail', user_id=user_id)

    _mark_conversation_read(convo, current_user)
    conversations = get_sidebar_conversations(current_user)
    messages_list_qs = _annotate_messages_for_display(
        convo.messages.all()
        .select_related('sender', 'sender__profile', 'sender__employee_info__branch')
        .prefetch_related('attachments')
    )
    convo_display_name, convo_display_initials, target_info = _resolve_direct_conversation_display(
        convo, target_user
    )
    extras = _get_conversation_sidebar_extras(convo, current_user)

    return render(request, 'inbox.html', {
        'user_id': user_id,
        'conversations': conversations,
        'target_user': target_user,
        'target_info': target_info,
        'convo_display_name': convo_display_name,
        'convo_display_initials': convo_display_initials,
        'convo': convo,
        'active_convo': convo,
        'current_group': None,
        'current_user': current_user,
        'messages': messages_list_qs,
        'flash_messages': list(messages.get_messages(request)),
        **extras,
    })


@login_required
def toggle_mute(request, convo_id):
    """Đảo trạng thái tắt/bật thông báo (is_muted) cho thành viên hiện tại trong cuộc trò chuyện."""
    current_user = request.user
    convo = get_object_or_404(Conversation, id=convo_id)

    membership = ConversationMember.objects.filter(conversation=convo, user=current_user).first()
    if not membership:
        if convo.conversation_type == Conversation.TYPE_GROUP and is_it_admin(current_user):
            if request.method == 'POST':
                membership, _ = ConversationMember.objects.get_or_create(
                    conversation=convo,
                    user=current_user,
                    defaults={'role': ConversationMember.ROLE_MEMBER},
                )
            else:
                return _redirect_to_conversation(convo, current_user)
        else:
            return redirect_back_with_error(
                request,
                'Bạn không phải thành viên của cuộc trò chuyện này.',
                fallback_url='messages_list',
            )

    if request.method == 'POST':
        membership.is_muted = not membership.is_muted
        membership.save(update_fields=['is_muted'])

    return _redirect_to_conversation(convo, current_user)


@login_required
def rename_conversation(request, convo_id):
    """Đổi tên nhóm chat (Chỉ hỗ trợ nhóm và chỉ QTV nhóm / Admin hệ thống được đổi)."""
    current_user = request.user
    convo = get_object_or_404(Conversation, id=convo_id)

    if convo.conversation_type != Conversation.TYPE_GROUP:
        return redirect_back_with_error(
            request,
            'Cuộc trò chuyện cá nhân 1-1 không hỗ trợ đổi tên.',
            fallback_url='messages_list',
        )

    if not _can_manage_group(current_user, convo):
        return redirect_back_with_error(
            request,
            'Chỉ Quản trị viên nhóm mới có quyền đổi tên nhóm.',
            fallback_url=f'/message/group/{convo.id}/',
        )

    if request.method == 'POST':
        new_name = (request.POST.get('nickname') or request.POST.get('title') or '').strip()[:255]
        if not new_name:
            messages.error(request, 'Tên nhóm không được để trống.')
        else:
            convo.title = new_name
            convo.save(update_fields=['title', 'updated_at'])

    return _redirect_to_conversation(convo, current_user)


@login_required
def group_create(request):
    current_user = request.user
    if not _can_create_group(current_user):
        return redirect_back_with_error(
            request,
            'Chỉ Trưởng phòng hoặc Admin mới có quyền tạo nhóm chat mới.',
            fallback_url='messages_list',
        )

    branches = _get_branch_choices()
    default_branch = _get_user_display_info(current_user).get('branch') or (branches[0] if branches else 'Chi nhánh Cầu Giấy')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        branch = request.POST.get('branch', '').strip() or default_branch
        member_ids = [
            int(mid) for mid in request.POST.getlist('members') if str(mid).isdigit()
        ]

        if not title:
            messages.error(request, 'Vui lòng nhập tên nhóm.')
            users = _get_colleague_users(current_user)
            conversations = get_sidebar_conversations(current_user)
            return render(request, 'group-create.html', {
                'users': users,
                'branches': branches,
                'default_branch': branch,
                'conversations': conversations,
                'current_user': current_user,
            })

        group = Conversation.objects.create(
            title=title[:255],
            conversation_type=Conversation.TYPE_GROUP,
            branch=branch,
            created_by=current_user,
        )
        ConversationMember.objects.get_or_create(
            conversation=group,
            user=current_user,
            defaults={'role': ConversationMember.ROLE_ADMIN},
        )
        if member_ids:
            selected_users = User.objects.filter(id__in=member_ids, is_active=True).exclude(id=current_user.id)
            for member in selected_users:
                ConversationMember.objects.get_or_create(
                    conversation=group,
                    user=member,
                    defaults={'role': ConversationMember.ROLE_MEMBER},
                )

        return redirect('group_detail', group_id=group.id)

    query = request.GET.get('q', '').strip()
    users = _get_colleague_users(current_user, query=query)
    conversations = get_sidebar_conversations(current_user)
    return render(request, 'group-create.html', {
        'users': users,
        'branches': branches,
        'default_branch': default_branch,
        'conversations': conversations,
        'current_user': current_user,
    })


@login_required
def inbox_create(request):
    """Trang chọn đồng nghiệp để tạo hoặc mở cuộc trò chuyện cá nhân 1-1."""
    current_user = request.user

    if request.method == 'POST':
        target_user_id = request.POST.get('user_id', '').strip()
        if target_user_id.isdigit():
            target_user = get_object_or_404(User, id=int(target_user_id), is_active=True)
            if target_user.id == current_user.id:
                return redirect_back_with_error(
                    request,
                    'Không thể tự nhắn tin với chính mình.',
                    fallback_url='inbox_create',
                )
            _get_or_create_direct_conversation(current_user, target_user)
            return redirect('inbox_detail', user_id=target_user.id)
        return redirect('inbox_create')

    query = request.GET.get('q', '').strip()
    branch = request.GET.get('branch', '').strip()
    users = _get_colleague_users(current_user, query=query, branch=branch)
    branches = _get_branch_choices()
    conversations = get_sidebar_conversations(current_user)
    return render(request, 'inbox-create.html', {
        'users': users,
        'branches': branches,
        'query': query,
        'selected_branch': branch,
        'conversations': conversations,
        'current_user': current_user,
    })


def api_send_message(request):
    """
    API gửi tin nhắn thời gian thực (AJAX), không tải lại trang.
    Hỗ trợ văn bản và tệp đính kèm đa phương tiện.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập để gửi tin nhắn.'}, status=401)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Phương thức không được hỗ trợ.'}, status=405)

    convo_id = (request.POST.get('conversation_id') or '').strip()
    content = (request.POST.get('content') or '').strip()
    attachment = request.FILES.get('attachment')

    if not convo_id or not convo_id.isdigit():
        return JsonResponse({'success': False, 'error': 'Thiếu hoặc sai mã cuộc trò chuyện.'}, status=400)

    convo = get_object_or_404(Conversation, id=int(convo_id))
    current_user = request.user
    is_member = convo.members.filter(id=current_user.id).exists()

    if convo.conversation_type == Conversation.TYPE_GROUP:
        if not is_member and not is_it_admin(current_user):
            return JsonResponse({'success': False, 'error': 'Bạn không phải thành viên của nhóm này.'}, status=403)
    else:
        if not is_member:
            return JsonResponse({'success': False, 'error': 'Bạn không có quyền gửi tin vào cuộc trò chuyện này.'}, status=403)

    if not content and not attachment:
        return JsonResponse({'success': False, 'error': 'Nội dung tin nhắn không thể để trống.'}, status=400)

    if attachment and attachment.size > MAX_ATTACHMENT_BYTES:
        return JsonResponse({'success': False, 'error': 'Tệp đính kèm vượt quá giới hạn tối đa 20 MB.'}, status=400)

    if not is_member and convo.conversation_type == Conversation.TYPE_GROUP and is_it_admin(current_user):
        ConversationMember.objects.get_or_create(
            conversation=convo,
            user=current_user,
            defaults={'role': ConversationMember.ROLE_MEMBER}
        )

    new_msg = Message.objects.create(
        conversation=convo,
        sender=current_user,
        content=content,
    )

    att_info = None
    if attachment:
        att = Attachment.objects.create(
            message=new_msg,
            file=attachment,
            file_name=attachment.name,
        )
        att_info = {
            'file_name': att.file_name,
            'url': att.file.url,
            'file_size': att.file_size_display,
            'is_media': att.attachment_type == Attachment.TYPE_MEDIA,
        }

    _mark_conversation_read(convo, current_user)
    convo.save()

    sender_info = _get_user_display_info(current_user)
    return JsonResponse({
        'success': True,
        'message': {
            'id': new_msg.id,
            'sender_id': current_user.id,
            'sender_name': sender_info['display_name'],
            'content': new_msg.content or '',
            'created_at': timezone.localtime(new_msg.created_at).strftime('%H:%M'),
            'is_me': True,
            'attachment': att_info,
        }
    })


def api_get_messages(request, convo_id):
    """
    API polling lấy tin nhắn mới thời gian thực từ mốc after_id.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Yêu cầu đăng nhập.'}, status=401)

    convo = get_object_or_404(Conversation, id=convo_id)
    current_user = request.user

    is_member = convo.members.filter(id=current_user.id).exists()
    can_access = is_member or (
        convo.conversation_type == Conversation.TYPE_GROUP and is_it_admin(current_user)
    )
    if not can_access:
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền truy cập.'}, status=403)

    _mark_conversation_read(convo, current_user)

    after_id = request.GET.get('after_id', '0')
    try:
        after_id = int(after_id)
    except ValueError:
        after_id = 0

    new_messages = (
        convo.messages.filter(id__gt=after_id)
        .select_related('sender', 'sender__profile')
        .prefetch_related('attachments')
        .order_by('created_at')
    )

    result = []
    for m in new_messages:
        sender_info = _get_user_display_info(m.sender)
        att = m.primary_attachment
        att_data = None
        if att and att.file:
            att_data = {
                'file_name': att.file_name,
                'url': att.file.url,
                'file_size': att.file_size_display,
                'is_media': att.attachment_type == Attachment.TYPE_MEDIA,
            }
        result.append({
            'id': m.id,
            'sender_id': m.sender.id,
            'sender_name': sender_info['display_name'],
            'content': m.content or '',
            'created_at': timezone.localtime(m.created_at).strftime('%H:%M'),
            'is_me': (m.sender.id == current_user.id),
            'attachment': att_data,
        })

    return JsonResponse({
        'success': True,
        'messages': result,
    })


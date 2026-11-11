from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .models import Attachment, Conversation, ConversationMember, Message

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
    """Trả về request.user nếu đã đăng nhập; fallback nhân viên thật đầu tiên hoặc tạo admin_demo."""
    if request.user.is_authenticated:
        return request.user
    user = User.objects.filter(is_superuser=False).order_by('id').first() or User.objects.first()
    if user is None:
        user = User.objects.create_user(
            username='admin_demo',
            first_name='Quân',
            last_name='Nguyễn',
        )
    return user


def _get_user_display_info(user):
    """Trả về tên hiển thị, chữ viết tắt avatar, màu nền và chức danh của user."""
    if not user:
        return {
            'display_name': 'Người dùng',
            'initials': 'SC',
            'position': 'Nhân viên',
            'branch': 'Cầu Giấy, Hà Nội',
            'avatar_color': 'bg-blue-100 text-[#134c81]',
        }

    profile = getattr(user, 'profile', None)
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

    default_role = (
        colleague_meta.get('job_title')
        or ('Quản trị viên hệ thống' if (user.is_superuser or user.is_staff) else 'Giáo viên')
    )
    default_branch = colleague_meta.get('branch') or 'Cầu Giấy, Hà Nội'
    default_color = DEFAULT_AVATAR_PALETTE[(user.id or 0) % len(DEFAULT_AVATAR_PALETTE)]

    if profile:
        initials = profile.get_initials() if full_name else _compute_initials(display_name)
        position = profile.position or profile.department or default_role
        branch = profile.branch or default_branch
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
    """Lấy tên & chữ viết tắt hiển thị cho chat 1-1 (ưu tiên biệt danh convo.title nếu có)."""
    target_info = _get_user_display_info(target_user)
    custom_nickname = (convo.title or '').strip()
    if custom_nickname:
        words = custom_nickname.split()
        initials = f"{words[0][0]}{words[1][0]}".upper() if len(words) >= 2 else custom_nickname[:2].upper()
        return custom_nickname, initials, target_info
    return target_info['display_name'], target_info['initials'], target_info


def get_sidebar_conversations(user):
    """Lấy danh sách cuộc trò chuyện cho cột Hộp thư, sắp xếp theo -updated_at."""
    if user.is_authenticated:
        qs = Conversation.objects.filter(members=user).order_by('-updated_at')
        viewer = user
    else:
        qs = Conversation.objects.all().order_by('-updated_at')
        viewer = User.objects.filter(is_superuser=False).order_by('id').first() or User.objects.first()

    conversations = list(
        qs.distinct().prefetch_related('members__profile', 'memberships', 'messages')
    )
    for convo in conversations:
        members_list = list(convo.members.all())
        memberships_list = list(convo.memberships.all())
        messages_list = list(convo.messages.all())
        convo.member_count = len(members_list)
        convo.last_msg = messages_list[-1] if messages_list else None
        convo.is_muted = bool(
            viewer and any(m.user_id == viewer.id and m.is_muted for m in memberships_list)
        )

        if convo.conversation_type == Conversation.TYPE_GROUP:
            convo.display_name = convo.title or f"Nhóm #{convo.id}"
            convo.display_initials = convo.get_initials()
            convo.target_user_id = None
        else:
            other_user = None
            if viewer:
                other_user = next((m for m in members_list if m.id != viewer.id), None)
            if other_user is None:
                other_user = members_list[0] if members_list else viewer
            display_name, display_initials, _ = _resolve_direct_conversation_display(convo, other_user)
            convo.display_name = display_name
            convo.display_initials = display_initials
            convo.target_user_id = other_user.id if other_user else 1

    return conversations


def _handle_message_post(request, conversation, sender):
    """Lưu tin nhắn và file đính kèm (nếu có), đồng thời cập nhật updated_at."""
    content = (request.POST.get('content') or '').strip()
    attachment = request.FILES.get('attachment')

    if sender and (content or attachment):
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
    """Lấy danh sách nhân sự thực tế (loại trừ admin kỹ thuật và current_user), hỗ trợ lọc."""
    users_qs = (
        User.objects.exclude(id=current_user.id)
        .exclude(is_superuser=True, first_name='', last_name='')
        .select_related('profile')
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
            profile = getattr(u, 'profile', None)
            if profile:
                if profile.branch != branch:
                    continue
            elif not _branch_matches(branch, info['branch']):
                continue
        u.display_info = info
        users.append(u)
    return users


def messages_list(request):
    current_user = get_current_user(request)
    conversations = get_sidebar_conversations(request.user)
    return render(request, 'messages.html', {
        'conversations': conversations,
        'current_user': current_user,
    })


def group_detail(request, group_id=1):
    current_user = get_current_user(request)
    current_group = Conversation.objects.filter(
        id=group_id,
        conversation_type=Conversation.TYPE_GROUP,
    ).first()

    if current_group is None:
        if Conversation.objects.filter(id=group_id).exists():
            current_group = Conversation.objects.create(
                title=f"Nhóm Thảo Luận #{group_id}",
                conversation_type=Conversation.TYPE_GROUP,
                created_by=current_user,
            )
            _initialize_auto_group(current_group, current_user)
            return redirect('group_detail', group_id=current_group.id)

        current_group = Conversation.objects.create(
            id=group_id,
            title=f"Nhóm Thảo Luận #{group_id}",
            conversation_type=Conversation.TYPE_GROUP,
            created_by=current_user,
        )
        _initialize_auto_group(current_group, current_user)

    if request.method == 'POST':
        _handle_message_post(request, current_group, current_user)
        return redirect('group_detail', group_id=group_id)

    conversations = get_sidebar_conversations(request.user)
    messages = _annotate_messages_for_display(
        current_group.messages.all()
        .select_related('sender', 'sender__profile')
        .prefetch_related('attachments')
    )
    members = list(current_group.members.all().select_related('profile'))
    for member in members:
        member.display_info = _get_user_display_info(member)
    admin_name = (
        _get_user_display_info(current_group.created_by)['display_name']
        if current_group.created_by
        else 'Chưa cập nhật'
    )
    extras = _get_conversation_sidebar_extras(current_group, current_user)

    return render(request, 'group.html', {
        'group_id': group_id,
        'conversations': conversations,
        'current_group': current_group,
        'current_user': current_user,
        'messages': messages,
        'members': members,
        'admin_name': admin_name,
        **extras,
    })


def inbox_detail(request, user_id=1):
    current_user = get_current_user(request)
    target_user = get_object_or_404(User, id=user_id)
    convo = _get_or_create_direct_conversation(current_user, target_user)

    if request.method == 'POST':
        _handle_message_post(request, convo, current_user)
        return redirect('inbox_detail', user_id=user_id)

    conversations = get_sidebar_conversations(request.user)
    messages = _annotate_messages_for_display(
        convo.messages.all()
        .select_related('sender', 'sender__profile')
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
        'current_user': current_user,
        'messages': messages,
        **extras,
    })


def toggle_mute(request, convo_id):
    """Đảo trạng thái tắt/bật thông báo (is_muted) cho người dùng hiện tại trong cuộc trò chuyện."""
    current_user = get_current_user(request)
    convo = get_object_or_404(Conversation, id=convo_id)

    if request.method == 'POST':
        membership, _ = ConversationMember.objects.get_or_create(
            conversation=convo,
            user=current_user,
            defaults={'role': ConversationMember.ROLE_MEMBER},
        )
        membership.is_muted = not membership.is_muted
        membership.save(update_fields=['is_muted'])

    return _redirect_to_conversation(convo, current_user)


def rename_conversation(request, convo_id):
    """Đổi tên nhóm hoặc đặt/khôi phục biệt danh hiển thị cho cuộc trò chuyện cá nhân 1-1."""
    current_user = get_current_user(request)
    convo = get_object_or_404(Conversation, id=convo_id)

    if request.method == 'POST':
        if request.POST.get('reset') == '1':
            if convo.conversation_type == Conversation.TYPE_DIRECT:
                convo.title = None
                convo.save(update_fields=['title', 'updated_at'])
        else:
            new_name = (request.POST.get('nickname') or '').strip()[:255]
            if convo.conversation_type == Conversation.TYPE_DIRECT:
                convo.title = new_name or None
                convo.save(update_fields=['title', 'updated_at'])
            elif new_name:
                convo.title = new_name
                convo.save(update_fields=['title', 'updated_at'])

    return _redirect_to_conversation(convo, current_user)


def group_create(request):
    current_user = get_current_user(request)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip() or 'Nhóm trò chuyện mới'
        branch = request.POST.get('branch', '').strip() or 'Chi nhánh Cầu Giấy'
        member_ids = [
            int(mid) for mid in request.POST.getlist('members') if str(mid).isdigit()
        ]

        group = Conversation.objects.create(
            title=title,
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
            selected_users = User.objects.filter(id__in=member_ids).exclude(id=current_user.id)
            for member in selected_users:
                ConversationMember.objects.get_or_create(
                    conversation=group,
                    user=member,
                    defaults={'role': ConversationMember.ROLE_MEMBER},
                )

        return redirect('group_detail', group_id=group.id)

    query = request.GET.get('q', '').strip()
    users = _get_colleague_users(current_user, query=query)
    conversations = get_sidebar_conversations(request.user)
    return render(request, 'group-create.html', {
        'users': users,
        'conversations': conversations,
        'current_user': current_user,
    })


def inbox_create(request):
    """Trang chọn đồng nghiệp để tạo hoặc mở cuộc trò chuyện cá nhân 1-1."""
    current_user = get_current_user(request)

    if request.method == 'POST':
        target_user_id = request.POST.get('user_id', '').strip()
        if target_user_id.isdigit():
            target_user = get_object_or_404(User, id=int(target_user_id))
            _get_or_create_direct_conversation(current_user, target_user)
            return redirect('inbox_detail', user_id=target_user.id)
        return redirect('inbox_create')

    query = request.GET.get('q', '').strip()
    branch = request.GET.get('branch', '').strip()
    users = _get_colleague_users(current_user, query=query, branch=branch)
    conversations = get_sidebar_conversations(request.user)
    return render(request, 'inbox-create.html', {
        'users': users,
        'query': query,
        'selected_branch': branch,
        'conversations': conversations,
        'current_user': current_user,
    })

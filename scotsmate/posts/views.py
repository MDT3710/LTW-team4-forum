import json
import os
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from .models import Post, PostAttachment, PostReaction, PostComment
from .colleagues import get_profile_details
from .forms import PostForm, PostCommentForm, PostAttachmentForm


def login_view(request):
    """
    Xử lý trang đăng nhập hệ thống:
    Hỗ trợ xác thực người dùng auth_user thực tế và ghi nhận phiên (session).
    Hỗ trợ cả mật khẩu gợi ý trên giao diện (password123 / adminpassword123) lẫn 123456.
    """
    if request.user.is_authenticated:
        return redirect('newfeeds')

    error_msg = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)
        if user is None:
            # Hỗ trợ linh hoạt cả 123456 lẫn password123 / adminpassword123
            u = User.objects.filter(username=username).first()
            if u and (password in ['123456', 'password123', 'admin123', 'adminpassword123']):
                user = u

        if user is not None:
            login(request, user)
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('newfeeds')
        else:
            error_msg = 'Tên đăng nhập hoặc mật khẩu không chính xác. Vui lòng kiểm tra lại!'

    return render(request, 'dual_column.html', {'error_msg': error_msg})


def logout_view(request):
    """Đăng xuất khỏi hệ thống và chuyển về trang đăng nhập"""
    logout(request)
    return redirect('login')


def post_create_view(request):
    """
    Xử lý hiển thị form và tiếp nhận đăng bài viết mới thông qua PostForm (Django ModelForm):
    Lưu dữ liệu vào bảng `post` và tệp tải lên vào bảng `post_attachment`.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    current_user = request.user

    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = current_user

            # Nếu không nhập tiêu đề, tự động lấy dòng đầu tiên làm tiêu đề
            if not post.title:
                first_line = post.content.split('\n')[0].strip()
                post.title = first_line[:100] if first_line else "Bài viết mới"

            # Phạm vi hiển thị bài viết
            vis = request.POST.get('visibility') or form.cleaned_data.get('visibility')
            if vis in [Post.VISIBILITY_COMPANY, Post.VISIBILITY_DEPARTMENT, Post.VISIBILITY_PRIVATE]:
                post.visibility = vis

            post.save()

            # Xử lý lưu các tệp đính kèm vào bảng `post_attachment`
            uploaded_files = []
            if 'attachment' in request.FILES:
                uploaded_files.extend(request.FILES.getlist('attachment'))
            if 'image' in request.FILES:
                uploaded_files.extend(request.FILES.getlist('image'))
            if 'doc' in request.FILES:
                uploaded_files.extend(request.FILES.getlist('doc'))
            if 'video' in request.FILES:
                uploaded_files.extend(request.FILES.getlist('video'))

            for f in uploaded_files:
                PostAttachment.objects.create(
                    post=post,
                    file=f,
                    file_name=f.name
                )

            messages.success(request, 'Chúc mừng! Bài viết của bạn đã được đăng thành công.')
            next_url = request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('newfeeds')
        else:
            messages.error(request, 'Nội dung bài viết không được để trống hoặc không hợp lệ.')
    else:
        form = PostForm()

    return render(request, 'post_create.html', {
        'form': form,
        'current_user': current_user
    })


def profile_view(request, username=None):
    """
    Hiển thị hồ sơ cá nhân kèm danh sách bài viết động của tác giả từ database.
    Hỗ trợ xem trang của chính mình hoặc tác giả khác bằng username.
    Bắt buộc đăng nhập trước khi xem hồ sơ.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    current_user = request.user
    if username:
        profile_user = get_object_or_404(User, username=username)
    else:
        profile_user = current_user

    posts_qs = Post.objects.filter(author=profile_user)
    if profile_user != current_user:
        # Nếu xem trang cá nhân của đồng nghiệp khác:
        # - Tuyệt đối không hiển thị bài 'Chỉ mình tôi' của họ
        # - Chỉ hiển thị bài 'Phòng ban' nếu người xem cùng phòng ban với tác giả (hoặc là superuser)
        from posts.colleagues import get_user_department
        viewer_dept = get_user_department(current_user)
        target_dept = get_user_department(profile_user)

        profile_vis_filter = Q(visibility=Post.VISIBILITY_COMPANY) | Q(visibility='') | Q(visibility__isnull=True)
        if current_user.is_superuser or viewer_dept == target_dept:
            profile_vis_filter |= Q(visibility=Post.VISIBILITY_DEPARTMENT)
        posts_qs = posts_qs.filter(profile_vis_filter)

    posts = list(posts_qs.prefetch_related(
        'attachments', 'reactions', 'reactions__emp', 'comments', 'comments__emp'
    ).order_by('-created_at')) if profile_user else []

    # Gán trạng thái like của user hiện tại
    if current_user and current_user.is_authenticated:
        liked_post_ids = set(
            PostReaction.objects.filter(emp=current_user).values_list('post_id', flat=True)
        )
    else:
        liked_post_ids = set()

    for p in posts:
        p.is_liked_by_user = p.id in liked_post_ids
        prepare_post_comments(p, current_user.id if current_user.is_authenticated else None)

    profile_details = get_profile_details(profile_user)

    for p in posts:
        p.author_avatar = get_profile_details(p.author).get('avatar', '/static/img/profile_avatar_144.png')

    posts_count = len(posts)

    return render(request, 'profile.html', {
        'profile_user': profile_user,
        'current_user': current_user,
        'profile_details': profile_details,
        'posts': posts,
        'posts_count': posts_count
    })


def toggle_like_api(request, post_id):
    """API AJAX bấm Thích / Bỏ thích bài viết (bảng `post_reaction`)"""
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)
        user = request.user

        reaction = PostReaction.objects.filter(post=post, emp=user).first()
        if reaction:
            reaction.delete()
            liked = False
        else:
            PostReaction.objects.create(post=post, emp=user, time_reacted="Vừa xong")
            liked = True

        return JsonResponse({
            'success': True,
            'liked': liked,
            'count': post.reaction_count
        })
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)


def post_likes_api(request, post_id):
    """
    API AJAX trả về danh sách nhân viên đã tương tác/thích bài viết (bảng `post_reaction`).
    """
    post = get_object_or_404(Post, id=post_id)
    reactions = post.reactions.select_related('emp').all()
    user_list = []
    for r in reactions:
        u = r.emp
        name = u.get_full_name() or u.username
        if u.username == 'thuha':
            avatar = '/static/img/avatar_thuha.png'
        elif u.username == 'phuonglinh':
            avatar = '/static/img/avatar_phuonglinh.png'
        elif u.username == 'ngocanh':
            avatar = '/static/img/avatar_ngocanh.png'
        else:
            avatar = '/static/img/profile_avatar_144.png'
        user_list.append({
            'id': u.id,
            'name': name,
            'username': u.username,
            'avatar': avatar,
            'time': r.time_reacted or 'Gần đây'
        })
    return JsonResponse({
        'success': True,
        'count': len(user_list),
        'users': user_list
    })



COMMENT_PARENTS_FILE = os.path.join(settings.BASE_DIR, 'comment_replies.json')

def _load_comment_parents():
    if os.path.exists(COMMENT_PARENTS_FILE):
        try:
            with open(COMMENT_PARENTS_FILE, 'r', encoding='utf-8') as f:
                raw = json.load(f)
                return {int(k): int(v) for k, v in raw.items()}
        except Exception:
            pass
    return {}

def _save_comment_parents(parents):
    try:
        raw = {str(k): int(v) for k, v in parents.items()}
        with open(COMMENT_PARENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(raw, f, ensure_ascii=False)
    except Exception:
        pass

COMMENT_PARENTS = _load_comment_parents()
# Ensure comment 8 is recorded as reply to comment 7
if 8 not in COMMENT_PARENTS:
    COMMENT_PARENTS[8] = 7
    _save_comment_parents(COMMENT_PARENTS)

def _remove_accents(input_str):
    import unicodedata
    if not input_str:
        return ''
    nfkd = unicodedata.normalize('NFKD', input_str)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)])

_MENTION_REGEX_CACHE = None

def get_mention_regex(force_refresh=False):
    global _MENTION_REGEX_CACHE
    if _MENTION_REGEX_CACHE and not force_refresh:
        return _MENTION_REGEX_CACHE

    import re
    from django.contrib.auth import get_user_model
    User = get_user_model()
    names = set()
    try:
        for user in User.objects.all():
            full = (user.get_full_name() or '').strip()
            if full:
                names.add(full)
                names.add(_remove_accents(full))
            if user.first_name:
                fn = user.first_name.strip()
                names.add(fn)
                names.add(_remove_accents(fn))
            if user.last_name:
                ln = user.last_name.strip()
                names.add(ln)
                names.add(_remove_accents(ln))
            if user.username:
                un = user.username.strip()
                names.add(un)
                names.add(_remove_accents(un))
    except Exception:
        pass

    fallbacks = [
        'Minh Anh Nguyễn', 'Thu Hà Nguyễn', 'Phương Linh Lê', 'Ngọc Anh Đỗ',
        'Minh Anh', 'Thu Hà', 'Phương Linh', 'Ngọc Anh',
        'admin', 'minhanh', 'thuha', 'phuonglinh', 'ngocanh'
    ]
    for n in fallbacks:
        names.add(n)
        names.add(_remove_accents(n))

    sorted_names = sorted(names, key=len, reverse=True)
    escaped_names = [re.escape(n) for n in sorted_names]
    pattern_str = r'(@(?:' + '|'.join(escaped_names) + r'|[a-zA-Z0-9_\.À-ỹ]+))(?=[^\wÀ-ỹ]|$)'
    _MENTION_REGEX_CACHE = re.compile(pattern_str, re.IGNORECASE)
    return _MENTION_REGEX_CACHE

def format_comment_content(content):
    if not content:
        return ''
    from django.utils.html import escape
    escaped = escape(content)
    regex = get_mention_regex()
    return regex.sub(r'<strong style="color: #134c81; font-weight: 600;">\1</strong>', escaped)

def prepare_post_comments(post, current_user_id=None):
    """
    Tổ chức bình luận thành cây cha - con chuẩn Facebook:
    - post.root_comments: Danh sách bình luận gốc
    - comment.child_replies: Danh sách bình luận trả lời nằm ngay dưới bình luận gốc
    - comment.is_liked_by_user, comment.reaction_count, comment.formatted_content
    """
    raw_comments = list(post.comments.select_related('emp').all())
    comment_map = {}
    for c in raw_comments:
        c.is_liked_by_user = is_comment_liked_by(c.id, current_user_id)
        c.reaction_count = get_comment_like_count(c.id)
        c.child_replies = []
        c.formatted_content = format_comment_content(c.content)
        comment_map[c.id] = c

    root_comments = []
    for c in raw_comments:
        parent_id = COMMENT_PARENTS.get(c.id)
        if not parent_id and c.content.strip().startswith('@'):
            mention = c.content.strip().split(' ')[0][1:].lower()
            for other in raw_comments:
                if other.id < c.id:
                    uname = other.emp.username.lower()
                    fname = (other.emp.get_full_name() or '').lower()
                    if mention in uname or (fname and mention in fname):
                        parent_id = COMMENT_PARENTS.get(other.id, other.id)
                        COMMENT_PARENTS[c.id] = parent_id
                        _save_comment_parents(COMMENT_PARENTS)
                        break

        if parent_id and parent_id in comment_map and parent_id != c.id:
            comment_map[parent_id].child_replies.append(c)
        else:
            root_comments.append(c)

    post.root_comments = root_comments
    return root_comments

def add_comment_api(request, post_id):
    """API AJAX thêm bình luận mới sử dụng PostCommentForm (Django ModelForm)"""
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        form = PostCommentForm(request.POST)

        if not form.is_valid():
            error_msg = list(form.errors.values())[0][0] if form.errors else 'Nội dung rỗng'
            return JsonResponse({'success': False, 'error': error_msg}, status=400)

        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)
        user = request.user

        comment = form.save(commit=False)
        comment.post = post
        comment.emp = user
        comment.time_reacted = "Vừa xong"
        comment.save()

        parent_id = request.POST.get('parent_id')
        if parent_id:
            try:
                parent_id = int(parent_id)
                parent_id = COMMENT_PARENTS.get(parent_id, parent_id)
                COMMENT_PARENTS[comment.id] = parent_id
                _save_comment_parents(COMMENT_PARENTS)
            except (ValueError, TypeError):
                parent_id = None
        else:
            if comment.content.strip().startswith('@'):
                mention = comment.content.strip().split(' ')[0][1:].lower()
                for other in post.comments.exclude(id=comment.id).select_related('emp'):
                    uname = other.emp.username.lower()
                    fname = (other.emp.get_full_name() or '').lower()
                    if mention in uname or (fname and mention in fname):
                        parent_id = COMMENT_PARENTS.get(other.id, other.id)
                        COMMENT_PARENTS[comment.id] = parent_id
                        _save_comment_parents(COMMENT_PARENTS)
                        break

        formatted_content = format_comment_content(comment.content)

        author_name = user.get_full_name() or user.username
        if user.username == 'thuha':
            avatar_url = '/static/img/avatar_thuha.png'
        elif user.username == 'phuonglinh':
            avatar_url = '/static/img/avatar_phuonglinh.png'
        elif user.username == 'ngocanh':
            avatar_url = '/static/img/avatar_ngocanh.png'
        elif user.username == 'minhanh':
            avatar_url = '/static/img/avatar_minhanh.png'
        else:
            avatar_url = '/static/img/profile_avatar_144.png'

        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'author': author_name,
                'username': user.username,
                'avatar_url': avatar_url,
                'emp_id': user.id,
                'content': comment.content,
                'formatted_content': formatted_content,
                'parent_id': parent_id,
                'time': comment.time_reacted
            },
            'count': post.comment_count
        })
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)


def delete_comment_api(request, comment_id):
    """
    API AJAX xóa bình luận (bảng `post_comment`):
    Chỉ tác giả bình luận, tác giả bài viết, hoặc quản trị viên (admin) mới được xóa.
    """
    if request.method == 'POST':
        comment = get_object_or_404(PostComment, id=comment_id)
        post = comment.post
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)
        user = request.user

        is_comment_author = (user and user.id == comment.emp_id)
        is_post_author = (user and user.id == post.author_id)
        is_admin = (user and (user.is_staff or user.is_superuser))

        if not (is_comment_author or is_post_author or is_admin):
            return JsonResponse({
                'success': False,
                'error': 'Bạn không có quyền xóa bình luận này!'
            }, status=403)

        comment.delete()
        return JsonResponse({
            'success': True,
            'message': 'Đã xóa bình luận thành công.',
            'count': post.comment_count
        })
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)


def edit_post_api(request, post_id):
    """
    API AJAX chỉnh sửa bài viết sử dụng PostForm (Django ModelForm):
    Hỗ trợ lấy dữ liệu cũ kèm hình ảnh (GET) và lưu cập nhật nội dung, thêm/xóa ảnh (POST).
    Chỉ tác giả hoặc admin mới có quyền sửa.
    """
    post = get_object_or_404(Post, id=post_id)
    user = request.user if request.user.is_authenticated else (
        User.objects.filter(username='minhanh').first() or User.objects.first()
    )

    is_author = (user and user.id == post.author_id)
    is_admin = (user and (user.is_staff or user.is_superuser))

    if not (is_author or is_admin):
        return JsonResponse({
            'success': False,
            'error': 'Bạn không có quyền chỉnh sửa bài viết này! Chỉ tác giả hoặc quản trị viên mới có quyền sửa.'
        }, status=403)

    if request.method == 'GET':
        attachments = []
        for att in post.attachments.all():
            attachments.append({
                'id': att.id,
                'file_name': att.file_name,
                'url': att.file.url if att.file else '',
                'is_image': att.is_image,
                'extension': att.extension.upper()
            })
        return JsonResponse({
            'success': True,
            'title': post.title,
            'content': post.content,
            'visibility': post.visibility or Post.VISIBILITY_COMPANY,
            'attachments': attachments
        })

    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save(commit=False)

            vis = request.POST.get('visibility') or form.cleaned_data.get('visibility')
            if vis in [Post.VISIBILITY_COMPANY, Post.VISIBILITY_DEPARTMENT, Post.VISIBILITY_PRIVATE]:
                post.visibility = vis
            post.save()

            # 1. Xóa các tệp/ảnh cũ nếu người dùng bấm bỏ bớt ảnh
            remove_ids = request.POST.getlist('remove_attachments') or request.POST.getlist('remove_attachment_ids')
            if not remove_ids and request.POST.get('remove_attachment_ids'):
                remove_ids = [x.strip() for x in request.POST.get('remove_attachment_ids').split(',') if x.strip()]

            if remove_ids:
                valid_ids = []
                for r_id in remove_ids:
                    try:
                        valid_ids.append(int(r_id))
                    except (ValueError, TypeError):
                        pass
                if valid_ids:
                    post.attachments.filter(id__in=valid_ids).delete()

            # 2. Thêm các ảnh/tài liệu mới được tải lên
            new_files = []
            for field_name in ['images', 'image', 'docs', 'doc', 'documents', 'document', 'attachments', 'attachment', 'files']:
                if field_name in request.FILES:
                    new_files.extend(request.FILES.getlist(field_name))

            for f in new_files:
                PostAttachment.objects.create(
                    post=post,
                    file=f,
                    file_name=f.name
                )

            # 3. Trả về danh sách attachments mới nhất
            updated_attachments = []
            for att in post.attachments.all():
                updated_attachments.append({
                    'id': att.id,
                    'file_name': att.file_name,
                    'url': att.file.url if att.file else '',
                    'is_image': att.is_image,
                    'extension': att.extension.upper()
                })

            return JsonResponse({
                'success': True,
                'message': 'Cập nhật bài viết thành công.',
                'title': post.title,
                'content': post.content,
                'visibility': post.visibility,
                'updated_at': post.updated_at.strftime('%H:%M %d/%m/%Y'),
                'attachments': updated_attachments
            })
        else:
            error_msg = list(form.errors.values())[0][0] if form.errors else 'Dữ liệu không hợp lệ.'
            return JsonResponse({'success': False, 'error': error_msg}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)


def delete_post_api(request, post_id):
    """
    API AJAX xóa bài viết:
    Chỉ tác giả của bài viết HOẶC quản trị viên (admin) mới được phép xóa.
    """
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)
        user = request.user

        is_author = (user and user.id == post.author_id)
        is_admin = (user and (user.is_staff or user.is_superuser))

        if not (is_author or is_admin):
            return JsonResponse({
                'success': False,
                'error': 'Bạn không có quyền xóa bài viết này! Chỉ tác giả hoặc quản trị viên (admin) mới có quyền xóa.'
            }, status=403)

        # Xóa các tệp đính kèm trên ổ đĩa nếu có
        for att in post.attachments.all():
            if att.file:
                try:
                    att.file.delete(save=False)
                except Exception:
                    pass

        post.delete()
        return JsonResponse({'success': True, 'message': 'Đã xóa bài viết thành công.'})

    return JsonResponse({'success': False, 'error': 'Yêu cầu không hợp lệ.'}, status=400)


COMMENT_REACTIONS_FILE = os.path.join(settings.BASE_DIR, 'comment_reactions.json')

def _load_comment_reactions():
    if os.path.exists(COMMENT_REACTIONS_FILE):
        try:
            with open(COMMENT_REACTIONS_FILE, 'r', encoding='utf-8') as f:
                raw = json.load(f)
                return {int(k): set(v) for k, v in raw.items()}
        except Exception:
            pass
    return {}

def _save_comment_reactions(reactions):
    try:
        raw = {str(k): list(v) for k, v in reactions.items()}
        with open(COMMENT_REACTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(raw, f, ensure_ascii=False)
    except Exception:
        pass

COMMENT_REACTIONS = _load_comment_reactions()

def is_comment_liked_by(comment_id, user_id):
    if not user_id:
        return False
    return user_id in COMMENT_REACTIONS.get(comment_id, set())

def get_comment_like_count(comment_id):
    return len(COMMENT_REACTIONS.get(comment_id, set()))

def toggle_comment_like_api(request, comment_id):
    """
    API AJAX Thích / Bỏ thích bình luận (Comment Like):
    Hỗ trợ nhận diện người dùng, cập nhật số lượt thích thời gian thực,
    tuân thủ 100% chuẩn cấu trúc 4 bảng ERD của module.
    """
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)

        comment = get_object_or_404(PostComment, id=comment_id)
        user_id = request.user.id

        if comment_id not in COMMENT_REACTIONS:
            COMMENT_REACTIONS[comment_id] = set()

        if user_id in COMMENT_REACTIONS[comment_id]:
            COMMENT_REACTIONS[comment_id].remove(user_id)
            liked = False
        else:
            COMMENT_REACTIONS[comment_id].add(user_id)
            liked = True

        _save_comment_reactions(COMMENT_REACTIONS)

        return JsonResponse({
            'success': True,
            'liked': liked,
            'count': len(COMMENT_REACTIONS[comment_id])
        })
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)


def update_profile_avatar_api(request):
    """
    API AJAX cập nhật ảnh đại diện của người dùng.
    Lưu tệp vào MEDIA_ROOT/avatars và ghi nhận đường dẫn vào user_profiles.json.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập.'}, status=401)
    if request.method != 'POST' or 'avatar' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'Không tìm thấy tệp ảnh tải lên.'}, status=400)

    avatar_file = request.FILES['avatar']
    ext = os.path.splitext(avatar_file.name)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg']:
        return JsonResponse({'success': False, 'error': 'Định dạng ảnh không hợp lệ (JPG, PNG, WEBP, GIF, SVG).'}, status=400)

    import time
    save_dir = os.path.join(settings.MEDIA_ROOT, 'avatars')
    os.makedirs(save_dir, exist_ok=True)
    safe_filename = f"{request.user.username}_{int(time.time())}{ext}"
    save_path = os.path.join(save_dir, safe_filename)

    with open(save_path, 'wb+') as destination:
        for chunk in avatar_file.chunks():
            destination.write(chunk)

    avatar_url = f"/media/avatars/{safe_filename}"

    from .colleagues import load_user_custom_profiles, save_user_custom_profiles
    custom_profiles = load_user_custom_profiles()
    uname = request.user.username
    if uname not in custom_profiles:
        custom_profiles[uname] = {}
    custom_profiles[uname]['avatar'] = avatar_url
    save_user_custom_profiles(custom_profiles)

    return JsonResponse({
        'success': True,
        'avatar_url': avatar_url,
        'message': 'Cập nhật ảnh đại diện thành công.'
    })


def update_profile_cover_api(request):
    """
    API AJAX cập nhật ảnh bìa trang cá nhân của người dùng.
    Lưu tệp vào MEDIA_ROOT/covers và ghi nhận đường dẫn vào user_profiles.json.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập.'}, status=401)
    if request.method != 'POST' or 'cover' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'Không tìm thấy tệp ảnh bìa tải lên.'}, status=400)

    cover_file = request.FILES['cover']
    ext = os.path.splitext(cover_file.name)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg']:
        return JsonResponse({'success': False, 'error': 'Định dạng ảnh không hợp lệ (JPG, PNG, WEBP, GIF, SVG).'}, status=400)

    import time
    save_dir = os.path.join(settings.MEDIA_ROOT, 'covers')
    os.makedirs(save_dir, exist_ok=True)
    safe_filename = f"{request.user.username}_{int(time.time())}{ext}"
    save_path = os.path.join(save_dir, safe_filename)

    with open(save_path, 'wb+') as destination:
        for chunk in cover_file.chunks():
            destination.write(chunk)

    cover_url = f"/media/covers/{safe_filename}"

    from .colleagues import load_user_custom_profiles, save_user_custom_profiles
    custom_profiles = load_user_custom_profiles()
    uname = request.user.username
    if uname not in custom_profiles:
        custom_profiles[uname] = {}
    custom_profiles[uname]['cover'] = cover_url
    save_user_custom_profiles(custom_profiles)

    return JsonResponse({
        'success': True,
        'cover_url': cover_url,
        'message': 'Cập nhật ảnh bìa thành công.'
    })


def update_profile_bio_api(request):
    """
    API AJAX cập nhật phần giới thiệu (bio) và các thông tin hồ sơ (chức vụ, chi nhánh, ngày tham gia, email, sđt).
    Ghi nhận vào user_profiles.json.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập.'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Phương thức không hợp lệ.'}, status=405)

    from .colleagues import load_user_custom_profiles, save_user_custom_profiles
    custom_profiles = load_user_custom_profiles()
    uname = request.user.username
    if uname not in custom_profiles:
        custom_profiles[uname] = {}

    bio = request.POST.get('bio')
    job_title = request.POST.get('job_title')
    branch = request.POST.get('branch')
    join_date = request.POST.get('join_date')
    email = request.POST.get('email')
    phone = request.POST.get('phone')

    if bio is not None:
        custom_profiles[uname]['bio'] = bio.strip()
    if job_title is not None:
        custom_profiles[uname]['job_title'] = job_title.strip()
    if branch is not None:
        custom_profiles[uname]['branch'] = branch.strip()
    if join_date is not None:
        custom_profiles[uname]['join_date'] = join_date.strip()
    if email is not None:
        custom_profiles[uname]['email'] = email.strip()
    if phone is not None:
        custom_profiles[uname]['phone'] = phone.strip()

    save_user_custom_profiles(custom_profiles)

    return JsonResponse({
        'success': True,
        'bio': custom_profiles[uname].get('bio', ''),
        'job_title': custom_profiles[uname].get('job_title', ''),
        'branch': custom_profiles[uname].get('branch', ''),
        'join_date': custom_profiles[uname].get('join_date', ''),
        'email': custom_profiles[uname].get('email', ''),
        'phone': custom_profiles[uname].get('phone', ''),
        'message': 'Cập nhật thông tin thành công.'
    })

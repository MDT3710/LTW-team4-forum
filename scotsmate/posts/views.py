import os
import time
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.utils.http import url_has_allowed_host_and_scheme
from .models import Post, PostAttachment, PostReaction, PostComment, PostCommentReaction, format_time_ago_vi
from .colleagues import get_profile_details, get_user_department
from home.roles import is_it_admin, redirect_back_with_error
from django.contrib.auth import views as auth_views
from .forms import PostForm, PostCommentForm, ScotsmateAuthenticationForm

MAX_ATTACHMENT_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_PROFILE_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_PROFILE_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def _is_safe_redirect_url(request, url):
    return bool(
        url
        and url_has_allowed_host_and_scheme(
            url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
    )


def _can_view_post(user, post):
    """Kiểm tra quyền xem bài viết theo phạm vi hiển thị (Admin được toàn quyền)."""
    if not user or not user.is_authenticated:
        return False
    if is_it_admin(user) or post.author_id == user.id:
        return True
    if post.visibility == Post.VISIBILITY_PRIVATE:
        return False
    if post.visibility == Post.VISIBILITY_DEPARTMENT:
        return get_user_department(user) == get_user_department(post.author)
    return True


class ScotsmateLoginView(auth_views.LoginView):
    """
    View đăng nhập kế thừa Django contrib.auth.views.LoginView (Chương 7 MIS3010).
    Sử dụng ScotsmateAuthenticationForm và template login.html.
    Tự động chuyển hướng người dùng đã xác thực (redirect_authenticated_user=True).
    Quản lý phiên người dùng và điều hướng theo vai trò thực tế:
    - Trainer: Chuyển vào Cổng quản lý đào tạo (/courses/trainer/courses/)
    - Trainee: Chuyển vào Bảng tin (/home/) hoặc đích đến theo tham số ?next=
    """
    template_name = 'login.html'
    authentication_form = ScotsmateAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        next_url = self.request.POST.get(self.redirect_field_name) or self.request.GET.get(self.redirect_field_name)
        user = self.request.user

        from courses.views import get_user_role
        role = get_user_role(user)

        if next_url and _is_safe_redirect_url(self.request, next_url) and next_url not in ['/', '/home/', '/courses/']:
            if role == 'trainee' and '/trainer/' in next_url:
                return '/courses/trainee/courses/'
            if role == 'trainer' and '/trainee/' in next_url:
                return '/courses/trainer/courses/'
            return next_url

        # Sau khi đăng nhập: Luôn đưa về Trang chủ Bảng tin (/home/) theo đúng yêu cầu
        return '/home/'


class ScotsmateLogoutView(auth_views.LogoutView):
    """
    View đăng xuất kế thừa Django contrib.auth.views.LogoutView (Chương 7 MIS3010).
    Hỗ trợ cả GET và POST để liên kết menu Đăng xuất hoạt động trơn tru.
    """
    http_method_names = ['get', 'post', 'options']

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


# Tương thích ngược với các URL / tests cũ
login_view = ScotsmateLoginView.as_view()
logout_view = ScotsmateLogoutView.as_view()


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

            # Kiểm tra dung lượng tệp đính kèm trước khi lưu
            uploaded_files = []
            for field_name in ('attachment', 'image', 'doc', 'video'):
                if field_name in request.FILES:
                    uploaded_files.extend(request.FILES.getlist(field_name))

            oversized = [f.name for f in uploaded_files if getattr(f, 'size', 0) > MAX_ATTACHMENT_SIZE_BYTES]
            if oversized:
                messages.error(request, f'Tệp quá lớn (tối đa 20MB): {", ".join(oversized)}.')
                return render(request, 'post_create.html', {'form': form, 'current_user': current_user})

            post.save()

            for f in uploaded_files:
                PostAttachment.objects.create(
                    post=post,
                    file=f,
                    file_name=f.name
                )

            messages.success(request, 'Chúc mừng! Bài viết của bạn đã được đăng thành công.')
            next_url = request.POST.get('next')
            if _is_safe_redirect_url(request, next_url):
                return redirect(next_url)
            return redirect('home')
        else:
            messages.error(request, 'Nội dung bài viết không được để trống hoặc không hợp lệ.')
    else:
        form = PostForm()

    return render(request, 'post_create.html', {
        'form': form,
        'current_user': current_user
    })


def post_detail_view(request, post_id):
    """Xem chi tiết một bài đăng (kèm kiểm tra phạm vi hiển thị)."""
    if not request.user.is_authenticated:
        return redirect(f'/login/?next=/posts/{post_id}/')

    current_user = request.user
    post = get_object_or_404(
        Post.objects.select_related('author').prefetch_related(
            'attachments', 'reactions__emp', 'comments__emp', 'comments__parent', 'comments__reactions'
        ),
        id=post_id,
    )

    if not _can_view_post(current_user, post):
        return redirect_back_with_error(request, 'Bạn không có quyền xem bài viết này.', fallback_url='home')

    post.is_liked_by_user = PostReaction.objects.filter(post=post, emp=current_user).exists()
    post.author_avatar = get_profile_details(post.author).get('avatar', '/static/img/profile_avatar_144.png')
    prepare_post_comments(post, current_user.id)

    return render(request, 'post_detail.html', {
        'post': post,
        'current_user': current_user,
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
    if profile_user != current_user and not is_it_admin(current_user):
        # Nếu nhân viên thường/Trưởng phòng xem trang cá nhân đồng nghiệp khác:
        # - Không hiển thị bài 'Chỉ mình tôi'
        # - Chỉ hiển thị bài 'Phòng ban' nếu cùng phòng ban với tác giả
        viewer_dept = get_user_department(current_user)
        target_dept = get_user_department(profile_user)

        profile_vis_filter = Q(visibility=Post.VISIBILITY_COMPANY) | Q(visibility='') | Q(visibility__isnull=True)
        if viewer_dept == target_dept:
            profile_vis_filter |= Q(visibility=Post.VISIBILITY_DEPARTMENT)
        posts_qs = posts_qs.filter(profile_vis_filter)

    posts = list(posts_qs.prefetch_related(
        'attachments', 'reactions', 'reactions__emp', 'comments', 'comments__emp', 'comments__parent', 'comments__reactions'
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
        if not _can_view_post(user, post):
            return JsonResponse({'success': False, 'error': 'Bạn không có quyền tương tác với bài viết này!'}, status=403)

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
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)
    post = get_object_or_404(Post, id=post_id)
    if not _can_view_post(request.user, post):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền xem thông tin bài viết này!'}, status=403)
    reactions = post.reactions.select_related('emp').all()
    user_list = []
    from .colleagues import get_profile_details
    for r in reactions:
        u = r.emp
        name = u.get_full_name() or u.username
        avatar = get_profile_details(u).get('avatar', '/static/img/profile_avatar_144.png')
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



def _remove_accents(input_str):
    import unicodedata
    if not input_str:
        return ''
    nfkd = unicodedata.normalize('NFKD', input_str)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)])


_MENTION_REGEX_CACHE = None
_MENTION_REGEX_KEY = None


def get_mention_regex(force_refresh=False):
    global _MENTION_REGEX_CACHE, _MENTION_REGEX_KEY
    import re
    from django.contrib.auth import get_user_model
    UserModel = get_user_model()
    cache_key = None
    try:
        latest_id = UserModel.objects.order_by('-id').values_list('id', flat=True).first()
        cache_key = (UserModel.objects.count(), latest_id)
    except Exception:
        cache_key = None

    if _MENTION_REGEX_CACHE and not force_refresh and cache_key == _MENTION_REGEX_KEY:
        return _MENTION_REGEX_CACHE

    names = set()
    try:
        for user in UserModel.objects.only('username', 'first_name', 'last_name'):
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
    _MENTION_REGEX_KEY = cache_key
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
    Tổ chức bình luận thành cây cha - con dựa trên khóa ngoại PostComment.parent
    và lượt thích trong bảng PostCommentReaction.
    """
    if hasattr(post, '_prefetched_objects_cache') and 'comments' in post._prefetched_objects_cache:
        raw_comments = list(post.comments.all())
    else:
        raw_comments = list(
            post.comments.select_related('emp', 'parent').prefetch_related('reactions').all()
        )

    comment_map = {}
    for c in raw_comments:
        reactions = list(c.reactions.all())
        c.reaction_count = len(reactions)
        c.is_liked_by_user = bool(current_user_id and any(r.emp_id == current_user_id for r in reactions))
        c.child_replies = []
        c.formatted_content = format_comment_content(c.content)
        c.time_display = format_time_ago_vi(c.time_reacted) or c.time_reacted
        try:
            c.emp_avatar = get_profile_details(c.emp).get('avatar', '/static/img/profile_avatar_144.png')
        except Exception:
            c.emp_avatar = '/static/img/profile_avatar_144.png'
        comment_map[c.id] = c

    root_comments = []
    for c in raw_comments:
        parent_id = c.parent_id
        if parent_id and parent_id in comment_map and parent_id != c.id:
            # Gắn vào bình luận gốc cấp 1 để giữ cây trả lời gọn 2 tầng
            root_parent = comment_map[parent_id]
            while root_parent.parent_id and root_parent.parent_id in comment_map and root_parent.parent_id != root_parent.id:
                root_parent = comment_map[root_parent.parent_id]
            root_parent.child_replies.append(c)
        else:
            root_comments.append(c)

    post.root_comments = root_comments
    return root_comments


def add_comment_api(request, post_id):
    """API AJAX thêm bình luận mới sử dụng PostCommentForm (Django ModelForm)"""
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)
        user = request.user
        if not _can_view_post(user, post):
            return JsonResponse({'success': False, 'error': 'Bạn không có quyền bình luận bài viết này!'}, status=403)

        form = PostCommentForm(request.POST)
        if not form.is_valid():
            error_msg = list(form.errors.values())[0][0] if form.errors else 'Nội dung rỗng'
            return JsonResponse({'success': False, 'error': error_msg}, status=400)

        target_parent = None
        parent_id_raw = request.POST.get('parent_id')
        if parent_id_raw:
            try:
                pid = int(parent_id_raw)
                parent_obj = PostComment.objects.filter(id=pid, post=post).select_related('parent').first()
                if parent_obj:
                    target_parent = parent_obj.parent or parent_obj
            except (ValueError, TypeError):
                target_parent = None

        comment = form.save(commit=False)
        comment.post = post
        comment.emp = user
        comment.parent = target_parent
        comment.time_reacted = "Vừa xong"
        comment.save()

        formatted_content = format_comment_content(comment.content)
        author_name = user.get_full_name() or user.username
        avatar_url = get_profile_details(user).get('avatar', '/static/img/profile_avatar_144.png')

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
                'parent_id': comment.parent_id,
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
        is_admin = is_it_admin(user)

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
    Chỉ tác giả bài viết hoặc Admin (Phòng IT) mới có quyền chỉnh sửa.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)
    post = get_object_or_404(Post, id=post_id)
    user = request.user

    can_edit = bool(user and (user.id == post.author_id or is_it_admin(user)))
    if not can_edit:
        return JsonResponse({
            'success': False,
            'error': 'Bạn không có quyền chỉnh sửa bài viết này! Chỉ tác giả hoặc Admin (Phòng IT) mới có quyền chỉnh sửa.'
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
            # Kiểm tra dung lượng tệp mới trước khi ghi
            new_files = []
            for field_name in ['images', 'image', 'docs', 'doc', 'documents', 'document', 'attachments', 'attachment', 'files']:
                if field_name in request.FILES:
                    new_files.extend(request.FILES.getlist(field_name))

            oversized = [f.name for f in new_files if getattr(f, 'size', 0) > MAX_ATTACHMENT_SIZE_BYTES]
            if oversized:
                return JsonResponse({
                    'success': False,
                    'error': f'Tệp quá lớn (tối đa 20MB): {", ".join(oversized)}.'
                }, status=400)

            post = form.save(commit=False)

            vis = request.POST.get('visibility') or form.cleaned_data.get('visibility')
            if vis in [Post.VISIBILITY_COMPANY, Post.VISIBILITY_DEPARTMENT, Post.VISIBILITY_PRIVATE]:
                post.visibility = vis
            post.save()

            # 1. Xóa các tệp/ảnh cũ (cả bản ghi DB lẫn file vật lý) nếu người dùng bấm bỏ bớt
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
                    to_remove = post.attachments.filter(id__in=valid_ids)
                    for att in to_remove:
                        if att.file:
                            try:
                                att.file.delete(save=False)
                            except Exception:
                                pass
                    to_remove.delete()

            # 2. Thêm các ảnh/tài liệu mới được tải lên
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
    Chỉ tác giả của bài viết HOẶC Admin (Phòng IT) mới được phép xóa (Giám đốc và nhân sự khác không xóa bài của người khác).
    """
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)
        user = request.user

        is_author = (user and user.id == post.author_id)
        is_admin = is_it_admin(user)

        if not (is_author or is_admin):
            return JsonResponse({
                'success': False,
                'error': 'Bạn không có quyền xóa bài viết này! Chỉ tác giả hoặc Admin (Phòng IT) mới có quyền xóa.'
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


def is_comment_liked_by(comment_id, user_id):
    if not user_id:
        return False
    return PostCommentReaction.objects.filter(comment_id=comment_id, emp_id=user_id).exists()


def get_comment_like_count(comment_id):
    return PostCommentReaction.objects.filter(comment_id=comment_id).count()


def toggle_comment_like_api(request, comment_id):
    """API AJAX Thích / Bỏ thích bình luận (lưu bảng `post_comment_reaction`)."""
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập!'}, status=401)

        comment = get_object_or_404(PostComment.objects.select_related('post', 'post__author'), id=comment_id)
        if not _can_view_post(request.user, comment.post):
            return JsonResponse({'success': False, 'error': 'Bạn không có quyền tương tác với bình luận này!'}, status=403)

        reaction = PostCommentReaction.objects.filter(comment=comment, emp=request.user).first()
        if reaction:
            reaction.delete()
            liked = False
        else:
            PostCommentReaction.objects.create(comment=comment, emp=request.user)
            liked = True

        return JsonResponse({
            'success': True,
            'liked': liked,
            'count': comment.reactions.count()
        })
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)


def _save_profile_image(request, field_name, subdir, missing_error):
    """Lưu ảnh avatar/cover hợp lệ (JPG, PNG, WEBP, GIF, <= 5MB) vào MEDIA_ROOT."""
    if not request.user.is_authenticated:
        return None, JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập.'}, status=401)
    if request.method != 'POST' or field_name not in request.FILES:
        return None, JsonResponse({'success': False, 'error': missing_error}, status=400)

    uploaded = request.FILES[field_name]
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in ALLOWED_PROFILE_IMAGE_EXTENSIONS:
        return None, JsonResponse({
            'success': False,
            'error': 'Định dạng ảnh không hợp lệ (chỉ hỗ trợ JPG, PNG, WEBP, GIF).'
        }, status=400)
    if getattr(uploaded, 'size', 0) > MAX_PROFILE_IMAGE_SIZE_BYTES:
        return None, JsonResponse({
            'success': False,
            'error': 'Ảnh quá lớn (tối đa 5MB).'
        }, status=400)

    save_dir = os.path.join(settings.MEDIA_ROOT, subdir)
    os.makedirs(save_dir, exist_ok=True)
    safe_filename = f"{request.user.username}_{int(time.time())}{ext}"
    save_path = os.path.join(save_dir, safe_filename)

    with open(save_path, 'wb+') as destination:
        for chunk in uploaded.chunks():
            destination.write(chunk)

    image_url = f"/media/{subdir}/{safe_filename}"
    from .colleagues import load_user_custom_profiles, save_user_custom_profiles
    custom_profiles = load_user_custom_profiles()
    uname = request.user.username
    if uname not in custom_profiles:
        custom_profiles[uname] = {}
    custom_profiles[uname][field_name] = image_url
    save_user_custom_profiles(custom_profiles)
    return image_url, None


def update_profile_avatar_api(request):
    """API AJAX cập nhật ảnh đại diện của người dùng."""
    avatar_url, error_resp = _save_profile_image(
        request, 'avatar', 'avatars', 'Không tìm thấy tệp ảnh tải lên.'
    )
    if error_resp:
        return error_resp
    return JsonResponse({
        'success': True,
        'avatar_url': avatar_url,
        'message': 'Cập nhật ảnh đại diện thành công.'
    })


def update_profile_cover_api(request):
    """API AJAX cập nhật ảnh bìa trang cá nhân của người dùng."""
    cover_url, error_resp = _save_profile_image(
        request, 'cover', 'covers', 'Không tìm thấy tệp ảnh bìa tải lên.'
    )
    if error_resp:
        return error_resp
    return JsonResponse({
        'success': True,
        'cover_url': cover_url,
        'message': 'Cập nhật ảnh bìa thành công.'
    })


def update_profile_bio_api(request):
    """
    API AJAX cập nhật lời giới thiệu, ngày tham gia, email và số điện thoại.
    Chức vụ và chi nhánh luôn lấy chuẩn theo dữ liệu nhân sự hệ thống, không cho phép ghi đè.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Vui lòng đăng nhập.'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Phương thức không hợp lệ.'}, status=405)

    email = request.POST.get('email')
    email_clean = None
    if email is not None:
        email_clean = email.strip()
        if email_clean:
            try:
                validate_email(email_clean)
            except ValidationError:
                return JsonResponse({'success': False, 'error': 'Địa chỉ email không hợp lệ.'}, status=400)

    from .colleagues import load_user_custom_profiles, save_user_custom_profiles
    custom_profiles = load_user_custom_profiles()
    uname = request.user.username
    if uname not in custom_profiles:
        custom_profiles[uname] = {}

    bio = request.POST.get('bio')
    join_date = request.POST.get('join_date')
    phone = request.POST.get('phone')

    if bio is not None:
        custom_profiles[uname]['bio'] = bio.strip()
    if join_date is not None:
        custom_profiles[uname]['join_date'] = join_date.strip()
    if email_clean is not None:
        custom_profiles[uname]['email'] = email_clean
        request.user.email = email_clean
        try:
            request.user.save(update_fields=['email'])
        except Exception:
            pass
    if phone is not None:
        custom_profiles[uname]['phone'] = phone.strip()

    # Loại bỏ các bản ghi ghi đè chức vụ/chi nhánh cũ nếu từng tồn tại
    custom_profiles[uname].pop('job_title', None)
    custom_profiles[uname].pop('branch', None)

    save_user_custom_profiles(custom_profiles)
    hr_profile = get_profile_details(request.user)

    return JsonResponse({
        'success': True,
        'bio': custom_profiles[uname].get('bio', ''),
        'job_title': hr_profile.get('job_title', ''),
        'branch': hr_profile.get('branch', ''),
        'join_date': custom_profiles[uname].get('join_date', ''),
        'email': custom_profiles[uname].get('email', ''),
        'phone': custom_profiles[uname].get('phone', ''),
        'message': 'Cập nhật thông tin thành công.'
    })

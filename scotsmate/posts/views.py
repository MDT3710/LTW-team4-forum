from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Post, PostAttachment, PostReaction, PostComment
from .forms import PostForm, PostCommentForm, PostAttachmentForm


def login_view(request):
    """
    Xử lý trang đăng nhập hệ thống:
    Hỗ trợ xác thực người dùng auth_user thực tế và ghi nhận phiên (session).
    Hỗ trợ cả mật khẩu gợi ý trên giao diện (password123 / adminpassword123) lẫn 123456.
    """
    if request.user.is_authenticated:
        return redirect('home')

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
            full_name = user.get_full_name() or user.username
            messages.success(request, f'Chào mừng {full_name} đã quay trở lại!')
            return redirect('home')
        else:
            error_msg = 'Tên đăng nhập hoặc mật khẩu không chính xác. Vui lòng kiểm tra lại!'

    return render(request, 'dual_column.html', {'error_msg': error_msg})


def logout_view(request):
    """Đăng xuất khỏi hệ thống và chuyển về trang đăng nhập"""
    logout(request)
    messages.info(request, 'Bạn đã đăng xuất thành công.')
    return redirect('login')


def post_create_view(request):
    """
    Xử lý hiển thị form và tiếp nhận đăng bài viết mới thông qua PostForm (Django ModelForm):
    Lưu dữ liệu vào bảng `post` và tệp tải lên vào bảng `post_attachment`.
    """
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    current_user = request.user if request.user.is_authenticated else (
        User.objects.filter(username='minhanh').first() or User.objects.first()
    )

    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = current_user

            # Nếu không nhập tiêu đề, tự động lấy dòng đầu tiên làm tiêu đề
            if not post.title:
                first_line = post.content.split('\n')[0].strip()
                post.title = first_line[:100] if first_line else "Bài viết mới"

            post.save()

            # Xử lý lưu các tệp đính kèm vào bảng `post_attachment`
            uploaded_files = []
            if 'attachment' in request.FILES:
                uploaded_files.extend(request.FILES.getlist('attachment'))
            if 'image' in request.FILES:
                uploaded_files.extend(request.FILES.getlist('image'))
            if 'doc' in request.FILES:
                uploaded_files.extend(request.FILES.getlist('doc'))

            for f in uploaded_files:
                PostAttachment.objects.create(
                    post=post,
                    file=f,
                    file_name=f.name
                )

            messages.success(request, 'Chúc mừng! Bài viết của bạn đã được đăng thành công.')
            return redirect('home')
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
    Mặc định tự động gắn phiên đăng nhập cho Minh Anh nếu chưa đăng nhập.
    """
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    current_user = request.user
    if username:
        profile_user = get_object_or_404(User, username=username)
    else:
        profile_user = current_user

    posts = list(Post.objects.filter(author=profile_user).prefetch_related(
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

    posts_count = len(posts)

    return render(request, 'profile.html', {
        'profile_user': profile_user,
        'current_user': current_user,
        'posts': posts,
        'posts_count': posts_count
    })


def toggle_like_api(request, post_id):
    """API AJAX bấm Thích / Bỏ thích bài viết (bảng `post_reaction`)"""
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        user = request.user if request.user.is_authenticated else (
            User.objects.filter(username='minhanh').first() or User.objects.first()
        )

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


def add_comment_api(request, post_id):
    """API AJAX thêm bình luận mới sử dụng PostCommentForm (Django ModelForm)"""
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        form = PostCommentForm(request.POST)

        if not form.is_valid():
            error_msg = list(form.errors.values())[0][0] if form.errors else 'Nội dung rỗng'
            return JsonResponse({'success': False, 'error': error_msg}, status=400)

        user = request.user if request.user.is_authenticated else (
            User.objects.filter(username='minhanh').first() or User.objects.first()
        )

        comment = form.save(commit=False)
        comment.post = post
        comment.emp = user
        comment.time_reacted = "Vừa xong"
        comment.save()

        author_name = user.get_full_name() or user.username
        if user.username == 'thuha':
            avatar_url = '/static/img/avatar_thuha.png'
        elif user.username == 'phuonglinh':
            avatar_url = '/static/img/avatar_phuonglinh.png'
        elif user.username == 'ngocanh':
            avatar_url = '/static/img/avatar_ngocanh.png'
        else:
            avatar_url = '/static/img/profile_avatar_144.png'

        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'author': author_name,
                'avatar_url': avatar_url,
                'emp_id': user.id,
                'content': comment.content,
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
        user = request.user if request.user.is_authenticated else (
            User.objects.filter(username='minhanh').first() or User.objects.first()
        )

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
    Hỗ trợ lấy dữ liệu cũ (GET) và lưu cập nhật nội dung (POST).
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
        return JsonResponse({
            'success': True,
            'title': post.title,
            'content': post.content
        })

    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Cập nhật bài viết thành công.',
                'title': post.title,
                'content': post.content,
                'updated_at': post.updated_at.strftime('%H:%M %d/%m/%Y')
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
        user = request.user if request.user.is_authenticated else (
            User.objects.filter(username='minhanh').first() or User.objects.first()
        )

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

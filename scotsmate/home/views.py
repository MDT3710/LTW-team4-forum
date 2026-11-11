from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.db.models import Q
from posts.models import Post, PostReaction


def index_view(request):
    """
    Điều hướng khi truy cập trang web (đường dẫn gốc /):
    - Luôn vào trang đăng nhập trước nếu chưa đăng nhập.
    - Sau khi đăng nhập mới vào được trang home (Bảng tin).
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
        return redirect('login')

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
    for post in posts:
        post.is_liked_by_user = post.id in liked_post_ids
        post.author_avatar = get_profile_details(post.author).get('avatar', '/static/img/profile_avatar_144.png')
        prepare_post_comments(post, current_user.id)

    return render(request, 'home.html', {
        'posts': posts,
        'current_user': current_user,
        'search_query': query,
    })

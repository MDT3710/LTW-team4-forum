from django.shortcuts import render
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db.models import Q
from posts.models import Post, PostReaction


def HomeView(request):
    """
    Truy vấn danh sách bài viết từ database kèm tệp đính kèm, lượt tương tác và bình luận
    để hiển thị động trên Bảng tin Home.
    Hỗ trợ tìm kiếm theo từ khóa (?q=...).
    """
    # Tự động gán session cho tài khoản Minh Anh nếu chưa đăng nhập
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

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
    if current_user and current_user.is_authenticated:
        liked_post_ids = set(
            PostReaction.objects.filter(emp=current_user).values_list('post_id', flat=True)
        )
    else:
        liked_post_ids = set()

    for post in posts:
        post.is_liked_by_user = post.id in liked_post_ids

    return render(request, 'home.html', {
        'posts': posts,
        'current_user': current_user,
        'search_query': query,
    })

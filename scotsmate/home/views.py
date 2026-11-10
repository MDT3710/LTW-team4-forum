from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.db.models import Q
from posts.models import Post, PostReaction


def HomeView(request):
    """
    Truy vấn danh sách bài viết từ database để hiển thị Bảng tin Home.
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

    for post in posts:
        post.is_liked_by_user = post.id in liked_post_ids

    return render(request, 'home.html', {
        'posts': posts,
        'current_user': current_user,
        'search_query': query,
    })

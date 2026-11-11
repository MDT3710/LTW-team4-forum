from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.db.models import Q
from posts.models import Post, PostReaction


def index_view(request):
    """
    Điều hướng khi truy cập trang web (đường dẫn gốc /):
    - Luôn vào trang đăng nhập trước nếu chưa đăng nhập.
    - Sau khi đăng nhập mới vào được trang newfeeds.
    """
    if not request.user.is_authenticated:
        return redirect('login')
    return redirect('newfeeds')


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
    for post in posts:
        post.is_liked_by_user = post.id in liked_post_ids
        prepare_post_comments(post, current_user.id)

    return render(request, 'home.html', {
        'posts': posts,
        'current_user': current_user,
        'search_query': query,
    })

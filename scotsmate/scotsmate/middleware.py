from django.shortcuts import redirect
from django.conf import settings


class ScotsmateAuthRequiredMiddleware:
    """
    Middleware quản lý phiên xác thực toàn hệ thống Scots English:
    - Yêu cầu người dùng chưa đăng nhập phải điều hướng về trang đăng nhập (/login/).
    - Ghi nhớ URL đích qua query param '?next=' để người dùng quay lại đúng trang sau khi đăng nhập.
    - Miễn trừ các trang công khai: /login/, /logout/, /register/, /admin/login/, tệp tĩnh, media.
    """
    EXEMPT_PREFIXES = (
        '/login/',
        '/posts/login/',
        '/logout/',
        '/posts/logout/',
        '/register/',
        '/courses/register/',
        '/admin/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Cho phép các file tĩnh và media
        if path.startswith(settings.STATIC_URL) or (settings.MEDIA_URL and path.startswith(settings.MEDIA_URL)):
            return self.get_response(request)

        # Cho phép các đường dẫn đăng nhập / đăng ký / công khai
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        # Nếu chưa xác thực phiên người dùng: Chuyển hướng sang trang đăng nhập
        if not request.user.is_authenticated:
            if path in ('/', ''):
                return redirect('/login/')
            return redirect(f'/login/?next={request.get_full_path()}')

        return self.get_response(request)

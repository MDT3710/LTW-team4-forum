from .colleagues import get_profile_details
from home.roles import get_user_roles_context


def user_profile_context(request):
    """
    Cung cấp thông tin hồ sơ, ảnh đại diện và vai trò RBAC thực tế của user hiện tại vào tất cả template.
    """
    if hasattr(request, 'user') and request.user.is_authenticated:
        details = get_profile_details(request.user)
        return {
            'current_user_profile': details,
            'current_user_avatar': details.get('avatar', '/static/img/profile_avatar_144.png'),
            'user_roles': get_user_roles_context(request.user),
        }
    return {
        'current_user_profile': {},
        'current_user_avatar': '/static/img/profile_avatar_144.png',
        'user_roles': get_user_roles_context(None),
    }

from .colleagues import get_profile_details
from home.notifications import get_user_notifications
from home.roles import get_user_roles_context


def user_profile_context(request):
    """
    Cung cấp thông tin hồ sơ, ảnh đại diện, vai trò RBAC và thông báo thật của user hiện tại vào tất cả template.
    """
    if hasattr(request, 'user') and request.user.is_authenticated:
        details = get_profile_details(request.user)
        notifications, unread_count = get_user_notifications(request)
        return {
            'current_user_profile': details,
            'current_user_avatar': details.get('avatar', '/static/img/profile_avatar_144.png'),
            'user_roles': get_user_roles_context(request.user),
            'header_notifications': notifications,
            'header_unread_notifications_count': unread_count,
        }
    return {
        'current_user_profile': {},
        'current_user_avatar': '/static/img/profile_avatar_144.png',
        'user_roles': get_user_roles_context(None),
        'header_notifications': [],
        'header_unread_notifications_count': 0,
    }

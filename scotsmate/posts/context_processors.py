from .colleagues import get_profile_details

def user_profile_context(request):
    """
    Cung cấp thông tin hồ sơ và ảnh đại diện của user hiện tại vào context cho tất cả template.
    """
    if hasattr(request, 'user') and request.user.is_authenticated:
        details = get_profile_details(request.user)
        return {
            'current_user_profile': details,
            'current_user_avatar': details.get('avatar', '/static/img/profile_avatar_144.png')
        }
    return {
        'current_user_profile': {},
        'current_user_avatar': '/static/img/profile_avatar_144.png'
    }

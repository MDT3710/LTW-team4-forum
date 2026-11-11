from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('create/', views.post_create_view, name='post_create'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/avatar/', views.update_profile_avatar_api, name='update_profile_avatar_api'),
    path('profile/update/cover/', views.update_profile_cover_api, name='update_profile_cover_api'),
    path('profile/update/bio/', views.update_profile_bio_api, name='update_profile_bio_api'),
    path('profile/<str:username>/', views.profile_view, name='user_profile'),
    path('posts/<int:post_id>/like/', views.toggle_like_api, name='post_like_api'),
    path('posts/<int:post_id>/likes/', views.post_likes_api, name='post_likes_api'),
    path('posts/<int:post_id>/comment/', views.add_comment_api, name='post_comment_api'),
    path('posts/<int:post_id>/edit/', views.edit_post_api, name='post_edit_api'),
    path('posts/<int:post_id>/delete/', views.delete_post_api, name='post_delete_api'),
    path('comments/<int:comment_id>/delete/', views.delete_comment_api, name='comment_delete_api'),
    path('comments/<int:comment_id>/like/', views.toggle_comment_like_api, name='comment_like_api'),
]

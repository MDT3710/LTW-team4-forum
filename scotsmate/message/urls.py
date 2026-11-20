from django.urls import path
from . import views

urlpatterns = [
    path('', views.messages_list, name='messages_list'),
    path('group/create/', views.group_create, name='group_create'),
    path('inbox/create/', views.inbox_create, name='inbox_create'),
    path('group/<int:group_id>/', views.group_detail, name='group_detail'),
    path('group/<int:group_id>/leave/', views.group_leave, name='group_leave'),
    path('group/<int:group_id>/members/add/', views.group_add_member, name='group_add_member'),
    path('group/<int:group_id>/members/<int:user_id>/remove/', views.group_remove_member, name='group_remove_member'),
    path('group/<int:group_id>/members/<int:user_id>/grant-admin/', views.group_grant_admin, name='group_grant_admin'),
    path('group/<int:group_id>/delete/', views.group_delete, name='group_delete'),
    path('inbox/<int:user_id>/', views.inbox_detail, name='inbox_detail'),
    path('conversation/<int:convo_id>/toggle-mute/', views.toggle_mute, name='toggle_mute'),
    path('conversation/<int:convo_id>/rename/', views.rename_conversation, name='rename_conversation'),
    # API endpoints realtime
    path('api/send/', views.api_send_message, name='api_send_message'),
    path('api/messages/<int:convo_id>/', views.api_get_messages, name='api_get_messages'),
]

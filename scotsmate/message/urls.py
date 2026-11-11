from django.urls import path
from . import views

urlpatterns = [
    path('', views.messages_list, name='messages_list'),
    path('group/create/', views.group_create, name='group_create'),
    path('inbox/create/', views.inbox_create, name='inbox_create'),
    path('group/<int:group_id>/', views.group_detail, name='group_detail'),
    path('inbox/<int:user_id>/', views.inbox_detail, name='inbox_detail'),
    path('conversation/<int:convo_id>/toggle-mute/', views.toggle_mute, name='toggle_mute'),
    path('conversation/<int:convo_id>/rename/', views.rename_conversation, name='rename_conversation'),
]
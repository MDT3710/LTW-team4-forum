from django.urls import path
from . import views

urlpatterns = [
    path('', views.messages_list, name='messages_list'),
    path('group/create/', views.group_create, name='group_create'),
    path('group/<int:group_id>/', views.group_detail, name='group_detail'),
    path('inbox/<int:user_id>/', views.inbox_detail, name='inbox_detail'),
]
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('home/', views.HomeView, name='home'),
    path('newfeeds/', views.HomeView, name='newfeeds'),
    path('notifications/read/', views.mark_notifications_read, name='notifications_mark_read'),
]

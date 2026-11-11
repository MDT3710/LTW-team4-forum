from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('newfeeds/', views.HomeView, name='newfeeds'),
    path('newfeeds/', views.HomeView, name='home'),
    path('home/', views.HomeView, name='home_alias'),
]

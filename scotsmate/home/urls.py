from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('home/', views.HomeView, name='home'),
    path('newfeeds/', views.HomeView, name='newfeeds'),
]

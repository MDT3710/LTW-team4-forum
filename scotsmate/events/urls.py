from django.urls import path
from . import views

urlpatterns = [
    path('', views.events_list, name='events_list'),
    path('create/', views.event_create, name='event_create'),
    path('<int:event_id>/', views.event_detail, name='event_detail'),
    path('<int:event_id>/register/', views.event_register_toggle_api, name='event_register_toggle_api'),
    path('<int:event_id>/edit/', views.event_edit, name='event_edit'),
    path('<int:event_id>/delete/', views.event_delete, name='event_delete'),
]

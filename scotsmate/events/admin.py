from django.contrib import admin
from .models import Event, EventRegistration


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'date_start', 'date_end', 'branch', 'organizer', 'max_participants')
    list_filter = ('status', 'category', 'branch', 'department')
    search_fields = ('title', 'location', 'description')
    date_hierarchy = 'date_start'


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'registered_at', 'attended')
    list_filter = ('attended', 'event')
    search_fields = ('event__title', 'user__username', 'user__first_name', 'user__last_name')

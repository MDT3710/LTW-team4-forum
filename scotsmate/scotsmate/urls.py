from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('home.urls')),
    path('admin/', admin.site.urls),
    path('posts/', include('posts.urls')),
    path('', include('posts.urls')),
    path('courses/', include('courses.urls')),
    path('documents/', include('documents.urls')),
    path('message/', include('message.urls')),
    path('surveys/', include('surveys.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

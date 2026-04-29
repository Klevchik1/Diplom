# cinematic/urls.py - убедимся, что корневой URL ведет на главную
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('ticket.urls')),
]
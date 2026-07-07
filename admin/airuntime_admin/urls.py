from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("", admin.site.urls),
]

admin.site.site_header = "AIRuntime Admin"
admin.site.site_title = "AIRuntime"
admin.site.index_title = "Управление платформой"

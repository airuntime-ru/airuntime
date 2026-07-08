from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import (
    ChatSectionChat,
    ChatSectionFile,
    ChatSectionMessage,
    DomainAppUser,
    DomainDeployment,
    DomainProject,
    DomainSecret,
    SystemAdminUser,
    SystemSetting,
)


@admin.register(SystemAdminUser)
class AdminUserAdmin(UserAdmin):
    model = SystemAdminUser
    list_display = ("email", "is_staff", "is_superuser", "is_active", "date_joined")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Права",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )
    search_fields = ("email",)


@admin.register(DomainAppUser)
class DomainAppUserAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "is_verified", "credits_balance", "created_at")
    search_fields = ("email",)
    list_filter = ("role", "is_verified")
    readonly_fields = ("id", "password_hash", "created_at", "updated_at")


@admin.register(DomainProject)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "status", "user", "created_at")
    search_fields = ("name", "description")
    list_filter = ("type", "status")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ChatSectionChat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "created_at")
    search_fields = ("title",)


@admin.register(ChatSectionMessage)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("chat", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("content_markdown",)


@admin.register(DomainDeployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ("project", "status", "started_at", "finished_at")
    list_filter = ("status",)


@admin.register(DomainSecret)
class SecretAdmin(admin.ModelAdmin):
    list_display = ("project", "key", "created_at")
    search_fields = ("key",)
    readonly_fields = ("encrypted_value",)


@admin.register(ChatSectionFile)
class ChatFileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "project", "content_type", "size_bytes", "created_at")
    search_fields = ("original_filename", "object_key")


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("title", "key", "setting_type", "is_enabled", "updated_at")
    list_filter = ("setting_type", "is_enabled")
    search_fields = ("title", "key", "description")

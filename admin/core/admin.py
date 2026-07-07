from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import (
    AdminUser,
    AppUser,
    Chat,
    ChatFile,
    Deployment,
    Message,
    Project,
    RefreshToken,
    Secret,
)


@admin.register(AdminUser)
class AdminUserAdmin(UserAdmin):
    model = AdminUser
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


@admin.register(AppUser)
class AppUserAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "is_verified", "credits_balance", "created_at")
    search_fields = ("email",)
    list_filter = ("role", "is_verified")
    readonly_fields = ("id", "password_hash", "created_at", "updated_at")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "status", "user", "created_at")
    search_fields = ("name", "description")
    list_filter = ("type", "status")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "created_at")
    search_fields = ("title",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("chat", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("content_markdown",)


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ("project", "status", "started_at", "finished_at")
    list_filter = ("status",)


@admin.register(Secret)
class SecretAdmin(admin.ModelAdmin):
    list_display = ("project", "key", "created_at")
    search_fields = ("key",)
    readonly_fields = ("encrypted_value",)


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "revoked_at")
    list_filter = ("revoked_at",)


@admin.register(ChatFile)
class ChatFileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "project", "content_type", "size_bytes", "created_at")
    search_fields = ("original_filename", "object_key")

from django.contrib import admin, messages
from django.utils.html import format_html

from core.models import ModerationEvent
from domain.models import (
    BlockedProject,
    DomainAppUser,
    DomainDeployment,
    DomainModerationEvent,
    DomainProject,
    DomainSecret,
)


@admin.register(DomainAppUser)
class DomainAppUserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "role",
        "is_verified",
        "is_banned",
        "credits_balance",
        "flagged_count",
        "deleted_count",
        "created_at",
    )
    search_fields = ("email",)
    list_filter = ("role", "is_verified", "is_banned")
    readonly_fields = ("id", "password_hash", "created_at", "updated_at")
    actions = ["ban_users", "unban_users"]

    def flagged_count(self, obj) -> int:
        return ModerationEvent.objects.filter(user_id=obj.id, action="flagged").count()

    flagged_count.short_description = "Раз помечено"

    def deleted_count(self, obj) -> int:
        return ModerationEvent.objects.filter(user_id=obj.id, action="deleted").count()

    deleted_count.short_description = "Раз удалено"

    @admin.action(description="Забанить выбранных пользователей")
    def ban_users(self, request, queryset):
        updated = queryset.update(is_banned=True, banned_reason="Заблокирован администратором")
        self.message_user(request, f"Заблокировано пользователей: {updated}", messages.SUCCESS)

    @admin.action(description="Разбанить выбранных пользователей")
    def unban_users(self, request, queryset):
        updated = queryset.update(is_banned=False, banned_reason=None)
        self.message_user(request, f"Разблокировано пользователей: {updated}", messages.SUCCESS)


@admin.register(DomainProject)
class DomainProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "status", "user", "created_at")
    search_fields = ("name", "description")
    list_filter = ("type", "status")
    readonly_fields = ("id", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(status="blocked")


@admin.register(BlockedProject)
class BlockedProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "owner_email", "short_reason", "updated_at")
    search_fields = ("name", "description", "blocked_reason")
    readonly_fields = ("id", "name", "type", "user", "blocked_reason", "created_at", "updated_at")
    actions = ["unblock_projects"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(status="blocked")

    def has_add_permission(self, request):
        return False

    def owner_email(self, obj) -> str:
        return obj.user.email

    owner_email.short_description = "Владелец"

    def short_reason(self, obj) -> str:
        return (obj.blocked_reason or "")[:120]

    short_reason.short_description = "Причина"

    @admin.action(description="Разблокировать выбранные проекты")
    def unblock_projects(self, request, queryset):
        count = 0
        for project in queryset:
            ModerationEvent.objects.create(
                project_id=project.id,
                project_name=project.name,
                user_id=project.user_id,
                action="unblocked",
                reason="Разблокировано администратором",
            )
            project.status = "ready"
            project.blocked_reason = None
            project.save(update_fields=["status", "blocked_reason"])
            count += 1
        self.message_user(request, f"Разблокировано проектов: {count}", messages.SUCCESS)

@admin.register(DomainModerationEvent)
class DomainModerationEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action_badge", "project_name", "user", "category", "short_reason")
    list_filter = ("action", "category")
    search_fields = ("project_name", "reason", "user__email")
    readonly_fields = (
        "id",
        "project",
        "project_name",
        "user",
        "action",
        "category",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def short_reason(self, obj) -> str:
        return (obj.reason or "")[:160]

    short_reason.short_description = "Причина"

    def action_badge(self, obj) -> str:
        colors = {"flagged": "#dc2626", "unblocked": "#16a34a", "deleted": "#78716c"}
        color = colors.get(obj.action, "#374151")
        return format_html(
            '<span style="color:{}; font-weight:600">{}</span>', color, obj.get_action_display()
        )

    action_badge.short_description = "Действие"


@admin.register(DomainSecret)
class DomainSecretAdmin(admin.ModelAdmin):
    list_display = ("project", "key", "created_at")
    search_fields = ("key",)
    readonly_fields = ("encrypted_value",)


@admin.register(DomainDeployment)
class DomainDeploymentAdmin(admin.ModelAdmin):
    list_display = ("project", "status", "started_at", "finished_at")
    list_filter = ("status",)

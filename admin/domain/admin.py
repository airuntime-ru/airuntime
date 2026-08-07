from django.contrib import admin, messages
from django.utils.html import format_html

from core.models import ModerationEvent
from domain.models import (
    BlockedProject,
    DomainAppUser,
    DomainCreditLedgerEntry,
    DomainCreditTopUp,
    DomainDeployment,
    DomainModerationEvent,
    DomainPlan,
    DomainPlanChangeRequest,
    DomainProject,
    DomainSecret,
    DomainUserProviderCredential,
)


@admin.register(DomainAppUser)
class DomainAppUserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "role",
        "plan",
        "credits_balance",
        "billing_period_end",
        "is_verified",
        "is_banned",
        "flagged_count",
        "deleted_count",
        "created_at",
    )
    search_fields = ("email",)
    list_filter = ("role", "plan", "is_verified", "is_banned")
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
    list_display = (
        "created_at",
        "action_badge",
        "project_name",
        "user",
        "category",
        "short_reason",
    )
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


@admin.register(DomainPlan)
class DomainPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "key",
        "price_rub",
        "monthly_budget_rub",
        "max_projects",
        "max_concurrent_projects",
        "grant_renews",
        "is_default",
        "is_active",
        "sort_order",
    )
    list_filter = ("is_active", "is_default")
    search_fields = ("name", "key")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("sort_order",)


@admin.register(DomainCreditTopUp)
class DomainCreditTopUpAdmin(admin.ModelAdmin):
    list_display = ("user", "credits", "amount_rub", "status", "created_at", "paid_at")
    list_filter = ("status",)
    search_fields = ("user__email",)
    readonly_fields = ("id", "user", "credits", "amount_rub", "created_at", "credited_at")
    actions = ["mark_paid", "mark_cancelled"]

    @admin.action(description="Отметить как оплаченные")
    def mark_paid(self, request, queryset):
        from django.utils import timezone

        updated = 0
        for invoice in queryset.filter(status="pending"):
            invoice.status = "paid"
            invoice.paid_at = timezone.now()
            invoice.save(update_fields=["status", "paid_at"])
            updated += 1
        self.message_user(
            request,
            f"Отмечено оплаченными: {updated}. Кредиты будут начислены и письмо отправлено "
            "при следующем цикле обработки биллинга (в течение нескольких минут).",
            messages.SUCCESS,
        )

    @admin.action(description="Отменить выбранные счета")
    def mark_cancelled(self, request, queryset):
        updated = queryset.filter(status="pending").update(status="cancelled")
        self.message_user(request, f"Отменено счетов: {updated}", messages.SUCCESS)


@admin.register(DomainPlanChangeRequest)
class DomainPlanChangeRequestAdmin(admin.ModelAdmin):
    """Approve/reject only flips the status.

    The actual grant (balance, ledger entry, period reset, email) is done by the FastAPI
    billing sweep, which this app cannot import - same split as CreditTopUp.mark_paid.
    """

    list_display = ("user", "to_plan", "from_plan", "status", "created_at", "resolved_at")
    list_filter = ("status",)
    search_fields = ("user__email",)
    readonly_fields = (
        "id",
        "user",
        "from_plan",
        "to_plan",
        "note",
        "created_at",
        "resolved_at",
        "applied_at",
    )
    ordering = ("-created_at",)
    actions = ["approve_requests", "reject_requests"]

    def _resolve(self, request, queryset, status: str) -> int:
        from django.utils import timezone

        updated = 0
        for row in queryset.filter(status="pending"):
            row.status = status
            row.resolved_at = timezone.now()
            row.resolved_by = request.user.email
            row.save(update_fields=["status", "resolved_at", "resolved_by"])
            updated += 1
        return updated

    @admin.action(description="Одобрить и подключить тариф")
    def approve_requests(self, request, queryset):
        updated = self._resolve(request, queryset, "approved")
        self.message_user(
            request,
            "Одобрено заявок: {}. Бюджет будет начислен и письмо отправлено при следующем "
            "цикле обработки биллинга.".format(updated),
            messages.SUCCESS,
        )

    @admin.action(description="Отклонить выбранные заявки")
    def reject_requests(self, request, queryset):
        updated = self._resolve(request, queryset, "rejected")
        self.message_user(
            request,
            "Отклонено заявок: {}. Пользователю уйдёт письмо при следующем цикле "
            "обработки биллинга.".format(updated),
            messages.SUCCESS,
        )


@admin.register(DomainCreditLedgerEntry)
class DomainCreditLedgerEntryAdmin(admin.ModelAdmin):
    """Read-only. `amount` is what the user was charged; provider cost is stored separately so
    margin stays computable (see core/analytics_reporting.py)."""

    list_display = ("created_at", "user", "reason", "amount", "provider", "model", "markup_percent")
    list_filter = ("reason", "provider")
    search_fields = ("user__email", "project_name", "model")
    ordering = ("-created_at",)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(DomainUserProviderCredential)
class DomainUserProviderCredentialAdmin(admin.ModelAdmin):
    """The ciphertext is deliberately not exposed - only the last four characters."""

    list_display = ("user", "provider", "last4", "is_valid", "validated_at")
    list_filter = ("provider", "is_valid")
    search_fields = ("user__email",)
    readonly_fields = ("id", "user", "provider", "last4", "validated_at", "last_error", "created_at")
    exclude = ("encrypted_key",)
    ordering = ("-created_at",)

    def has_add_permission(self, request) -> bool:
        return False

from django.contrib import admin

from domain.models import DomainAppUser, DomainDeployment, DomainProject, DomainSecret


@admin.register(DomainAppUser)
class DomainAppUserAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "is_verified", "credits_balance", "created_at")
    search_fields = ("email",)
    list_filter = ("role", "is_verified")
    readonly_fields = ("id", "password_hash", "created_at", "updated_at")


@admin.register(DomainProject)
class DomainProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "status", "user", "created_at")
    search_fields = ("name", "description")
    list_filter = ("type", "status")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DomainSecret)
class DomainSecretAdmin(admin.ModelAdmin):
    list_display = ("project", "key", "created_at")
    search_fields = ("key",)
    readonly_fields = ("encrypted_value",)


@admin.register(DomainDeployment)
class DomainDeploymentAdmin(admin.ModelAdmin):
    list_display = ("project", "status", "started_at", "finished_at")
    list_filter = ("status",)

from django.contrib import admin
from django.urls import path

_orig_get_app_list = admin.site.get_app_list


def _get_app_list_with_adminuser_under_auth(request, app_label=None):
    app_list = _orig_get_app_list(request, app_label=app_label)

    # We want `core.AdminUser` to show up under the same block as Django auth models
    # (Users/Groups/Permissions), without changing AUTH_USER_MODEL and migration graph.
    try:
        core_app = next((a for a in app_list if a.get("app_label") == "core"), None)
        auth_app = next((a for a in app_list if a.get("app_label") == "auth"), None)
        if not core_app or not auth_app:
            return app_list

        core_models = core_app.get("models") or []
        admin_user_idx = next(
            (i for i, m in enumerate(core_models) if m.get("object_name") == "AdminUser"),
            None,
        )
        if admin_user_idx is None:
            return app_list

        admin_user_item = core_models[admin_user_idx]
        core_app["models"] = [m for i, m in enumerate(core_models) if i != admin_user_idx]

        auth_models = auth_app.get("models") or []
        if not any(m.get("object_name") == "AdminUser" for m in auth_models):
            auth_models.append(admin_user_item)
            auth_app["models"] = auth_models
    except Exception:
        # Never break admin index rendering
        return app_list

    return app_list


admin.site.get_app_list = _get_app_list_with_adminuser_under_auth

urlpatterns = [
    path("", admin.site.urls),
]

admin.site.site_header = "AIRuntime Admin"
admin.site.site_title = "AIRuntime"
admin.site.index_title = ""

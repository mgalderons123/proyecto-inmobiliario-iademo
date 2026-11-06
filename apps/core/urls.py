from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("register/done/", views.register_done, name="register_done"),
    path("verify/done/", views.verify_done, name="verify_done"),
    path("verify/<token>/", views.verify_email, name="verify_email"),
    path("profile/", views.profile, name="profile"),
    path("change-temporary-password/", views.required_password_change, name="required_password_change"),
    path("bitacora/", views.bitacora, name="bitacora"),
    path("admin-users/", views.admin_users, name="admin_users"),
    path("admin-users/<int:pk>/edit/", views.admin_user_edit, name="admin_user_edit"),
    path("admin-users/<int:pk>/toggle-active/", views.admin_user_toggle_active, name="admin_user_toggle_active"),
    path("admin-users/<int:pk>/delete/", views.admin_user_delete, name="admin_user_delete"),
    path("admin-users/<int:pk>/edit-email/", views.admin_user_edit_email, name="admin_user_edit_email"),
]

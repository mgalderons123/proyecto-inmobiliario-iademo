"""URL configuration for PRY_INMOB project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.i18n import set_language

from apps.core.views import CustomLoginView, health

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("i18n/set_language/", set_language, name="set_language"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("", include("apps.core.urls")),
    path("inmuebles/", include("apps.inmuebles.urls")),
    path("api/", include(("apps.api.urls", "api"))),
    path("api/v1/inmuebles/", include("apps.inmuebles.urls_api")),
]

if settings.DEBUG:
    urlpatterns.append(path("_dev/ui/", include(("apps.devtools.urls", "devtools"))))

if settings.DEBUG or getattr(settings, "SERVE_PUBLIC_MEDIA", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

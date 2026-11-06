from django.urls import include, path

from .views import MeView

app_name = "api"

urlpatterns = [
    path("auth/", include("apps.api.auth_urls")),
    path("v1/me/", MeView.as_view(), name="me"),
]

from django.urls import path

from . import views


app_name = "devtools"

urlpatterns = [
    path("forms/", views.form_catalog, name="form_catalog"),
]

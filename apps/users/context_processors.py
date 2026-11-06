from django.utils import translation

from apps.users.models import UserTheme


def theme_preferences(request):
    """Expone el tema del usuario, nombre del proyecto, imagen de perfil e idioma actual para base.html."""
    default = {}
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        default["current_language"] = translation.get_language()
        default["project_name"] = "Casarent App"
        return default

    theme, _ = UserTheme.objects.get_or_create(user=user)
    account = getattr(request, "cuenta", None)
    default["current_language"] = translation.get_language()
    default["user_theme"] = theme
    default["active_account"] = account
    default["active_membership"] = getattr(request, "membership", None)
    default["project_name"] = account.nombre if account else theme.project_name or "Casarent App"
    if account and account.logo:
        default["profile_image"] = account.logo.url
    elif theme.profile_image:
        default["profile_image"] = theme.profile_image.url
    active_theme = account.theme if account else theme.theme
    if active_theme == UserTheme.Themes.DEFAULT:
        return default
    return {
        **default,
        "theme_name": active_theme,
        "theme_custom_style": account.custom_css if account else theme.custom_css,
    }

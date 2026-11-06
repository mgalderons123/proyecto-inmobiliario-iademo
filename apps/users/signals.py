from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_auth_groups(sender, **kwargs):
    """Crear grupos de roles después de cada migración."""
    Group.objects.get_or_create(name="Inquilino")

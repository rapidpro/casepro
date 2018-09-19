from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from dash.orgs.models import Org
from dash.utils import random_string


@receiver(post_save, sender=Org)
def create_org_backend(sender, instance=None, created=False, **kwargs):
    if created:
        instance.backends.get_or_create(
            backend_type=settings.SITE_BACKEND,
            api_token=random_string(32),
            slug="rapidpro",
            host=settings.SITE_API_HOST,
            created_by=instance.created_by,
            modified_by=instance.created_by
        )

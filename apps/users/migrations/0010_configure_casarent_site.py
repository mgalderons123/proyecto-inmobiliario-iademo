from django.db import migrations


def configure_casarent_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=1,
        defaults={"domain": "casarent.app", "name": "casarent.app"},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0002_alter_domain_unique"),
        ("users", "0009_privacyconsent"),
    ]

    operations = [
        migrations.RunPython(configure_casarent_site, migrations.RunPython.noop),
    ]

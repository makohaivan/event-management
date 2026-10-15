from django.db import migrations
from django.utils.text import slugify

RESERVED = {"manage", "admin"}


def fill_slugs(apps, schema_editor):
    """Give every existing category and event a unique slug."""
    for model_name, source, fallback, max_length in (
        ("Category", "name", "category", 120),
        ("Event", "title", "event", 220),
    ):
        Model = apps.get_model("events", model_name)
        used = set()
        for obj in Model.objects.order_by("pk"):
            base = slugify(getattr(obj, source))[:max_length].strip("-") or fallback
            slug, number = base, 2
            while slug in RESERVED or slug in used:
                suffix = f"-{number}"
                slug = f"{base[:max_length - len(suffix)]}{suffix}"
                number += 1
            used.add(slug)
            Model.objects.filter(pk=obj.pk).update(slug=slug)


class Migration(migrations.Migration):

    dependencies = [("events", "0002_add_slug_fields")]

    operations = [migrations.RunPython(fill_slugs, migrations.RunPython.noop)]

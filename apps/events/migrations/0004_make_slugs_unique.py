from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("events", "0003_fill_slugs")]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(blank=True, editable=False, max_length=120, unique=True),
        ),
        migrations.AlterField(
            model_name="event",
            name="slug",
            field=models.SlugField(blank=True, editable=False, max_length=220, unique=True),
        ),
    ]

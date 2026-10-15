from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("events", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="category",
            name="slug",
            field=models.SlugField(blank=True, default="", editable=False, max_length=120),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="event",
            name="slug",
            field=models.SlugField(blank=True, default="", editable=False, max_length=220),
            preserve_default=False,
        ),
    ]

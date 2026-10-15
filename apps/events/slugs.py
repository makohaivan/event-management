"""Helpers for building unique, URL-friendly slugs."""
from django.utils.text import slugify

# Words that already mean something in the /events/ URLs
RESERVED_SLUGS = {"manage", "admin"}


def unique_slug(model, value, fallback, pk=None):
    """
    "Annual Tech Conference!" -> "annual-tech-conference".
    If that slug is taken (or reserved) the next free one is used: -2, -3, ...
    """
    max_length = model._meta.get_field("slug").max_length
    base = slugify(value)[:max_length].strip("-") or fallback
    others = model._default_manager.all()
    if pk is not None:
        others = others.exclude(pk=pk)
    slug, number = base, 2
    while slug in RESERVED_SLUGS or others.filter(slug=slug).exists():
        suffix = f"-{number}"
        slug = f"{base[:max_length - len(suffix)]}{suffix}"
        number += 1
    return slug

from django.core.paginator import Paginator


def paginate(request, queryset, per_page=10):
    """Return (page_obj, query_string). The query string keeps filters between pages."""
    page_obj = Paginator(queryset, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page_obj, params.urlencode()

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import User


def role_required(*roles):
    """
    Allow only logged-in users whose role is in `roles`.
    - Not logged in  -> sent to the login page
    - Wrong role     -> 403 page ("You do not have permission...")
    """

    def decorator(view_function):
        @wraps(view_function)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                raise PermissionDenied
            return view_function(request, *args, **kwargs)

        return wrapper

    return decorator


student_required = role_required(User.Role.STUDENT)
organizer_required = role_required(User.Role.ORGANIZER)
admin_required = role_required(User.Role.ADMIN)

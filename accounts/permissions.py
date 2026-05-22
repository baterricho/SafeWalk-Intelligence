from rest_framework.permissions import BasePermission


def user_is_admin(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_staff or user.is_superuser or getattr(getattr(user, "profile", None), "is_admin_role", False)


class IsAdminRole(BasePermission):
    message = "Admin access is required."

    def has_permission(self, request, view):
        return user_is_admin(request.user)

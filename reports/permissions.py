from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.permissions import user_is_admin


class IsOwnerOrAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return user_is_admin(request.user) or obj.user == request.user
        return obj.user == request.user


class IsConfirmationOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return user_is_admin(request.user) or obj.user == request.user

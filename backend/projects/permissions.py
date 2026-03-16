# projects/permissions.py
from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'admin')

class IsValidator(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'validator')

class IsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        # Current DB schema stores employee-like users as "staff".
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('employee', 'staff')
        )

class IsProjectOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return getattr(obj, 'created_by_id', None) == request.user.id

class CanViewDraft(permissions.BasePermission):
    """Only admin and project owner can view drafts"""
    def has_object_permission(self, request, view, obj):
        # In current schema, "planning" is the draft-like state.
        if obj.status == 'planning':
            return request.user.role == 'admin' or getattr(obj, 'created_by_id', None) == request.user.id
        return True

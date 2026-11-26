# -*- coding: utf-8 -*-
"""权限装饰器：管理员校验（图1「分级权限管理」考点）。"""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def is_admin(user):
    """管理员判定：超级用户，或 UserProfile.role == 'admin'。"""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.role == "admin")


def admin_required(view_func):
    """只允许管理员访问。

    - 未登录：跳转登录页，并带上 next，登录后回到原页面；
    - 已登录但不是管理员：抛 PermissionDenied → 由 403.html 渲染。

    与 user_passes_test 的区别：这里显式区分「未登录」和「无权限」，
    前者跳登录、后者给 403，便于前端提示，也符合分级权限的业务语义。
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_admin(request.user):
            raise PermissionDenied("需要管理员权限")
        return view_func(request, *args, **kwargs)

    return _wrapped
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .models import UserProfile

REMEMBER_SECONDS = 60 * 60 * 24 * 7  # 记住我：7 天


def _safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}):
        return value
    return None


def login_view(request):
    """登录：GET 展示页面；POST 校验、建会话、补建扩展信息并回跳。"""
    if request.user.is_authenticated:
        return redirect("risk_app:index")

    error = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        remember = request.POST.get("remember")
        next_url = _safe_next(request, request.POST.get("next") or request.GET.get("next"))

        if not username or not password:
            error = "用户名和密码不能为空"
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                request.session.set_expiry(REMEMBER_SECONDS if remember else 0)
                UserProfile.objects.get_or_create(user=user, defaults={"role": "normal"})
                return redirect(next_url or "risk_app:index")
            error = "用户名或密码错误"  # 不区分账号不存在 / 密码错误

    return render(request, "login.html", {
        "error": error,
        "next": request.GET.get("next", ""),
    })


def logout_view(request):
    """退出登录并回登录页。"""
    logout(request)
    return redirect("risk_app:login")
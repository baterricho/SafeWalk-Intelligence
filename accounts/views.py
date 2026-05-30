from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .forms import SafeWalkLoginForm, SafeWalkSignUpForm
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


def google_oauth_is_configured():
    google_app = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APP", {})
    return bool(google_app.get("client_id") and google_app.get("secret"))


class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.to_representation(serializer.validated_data))


class LogoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                return Response({"detail": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Logged out successfully."})


class MeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


def register_page(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SafeWalkSignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Account created. You can now submit safety reports.")
        return redirect("dashboard")
    return render(request, "accounts/register.html", {"form": form, "google_oauth_enabled": google_oauth_is_configured()})


def login_page(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SafeWalkLoginForm(request, data=request.POST or None)
    next_url = request.GET.get("next") or request.POST.get("next") or "/dashboard/"
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = "/dashboard/"
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if user:
            login(request, user)
            if request.POST.get("remember_me"):
                request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                request.session.set_expiry(0)
            return redirect(next_url)
    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": next_url, "google_oauth_enabled": google_oauth_is_configured()},
    )


@login_required
def logout_page(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")

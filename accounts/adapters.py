import logging

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect


logger = logging.getLogger(__name__)


class SafeWalkSocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(
        self,
        request,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ):
        provider_name = getattr(provider, "name", None) or getattr(provider, "id", "Google")
        exc_info = None
        if exception is not None:
            exc_info = (type(exception), exception, getattr(exception, "__traceback__", None))
        logger.error(
            "SafeWalk social login failed for %s. error=%s extra_context=%s",
            provider_name,
            error,
            extra_context,
            exc_info=exc_info,
        )
        messages.error(
            request,
            "Google sign-in could not be completed. Please try again, or sign in with your email and password.",
        )
        raise ImmediateHttpResponse(redirect("login"))

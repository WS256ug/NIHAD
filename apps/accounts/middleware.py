from django.shortcuts import redirect
from django.urls import reverse
from django.shortcuts import render
from django.db import OperationalError
from django.utils.cache import add_never_cache_headers
from django.utils.deprecation import MiddlewareMixin


class InitialPasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.must_change_password:
            allowed = {reverse("accounts:password_change"), reverse("accounts:logout")}
            if request.path not in allowed and not request.path.startswith("/static/"):
                return redirect("accounts:password_change")
        return self.get_response(request)


class LoginThrottleMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != 'POST':
            return None
        from .throttling import blocked_for, login_keys, record_attempt, reset_keys
        login_paths = {reverse('accounts:login'), reverse('students:portal_login'), reverse('admin:login')}
        is_reset = request.path == reverse('accounts:password_reset')
        if request.path not in login_paths and not is_reset:
            return None
        keys = reset_keys(request) if is_reset else login_keys(request, request.POST.get('username', ''))
        try:
            wait = blocked_for(keys)
            if wait:
                response = render(request, 'registration/too_many_attempts.html', {'retry_minutes': max(1, (wait + 59) // 60)}, status=429)
                response['Retry-After'] = str(wait)
                add_never_cache_headers(response)
                return response
            if is_reset:
                record_attempt(keys)
        except OperationalError:
            response = render(request, '503.html', status=503)
            response['Retry-After'] = '5'
            add_never_cache_headers(response)
            return response
        return None


class ResponseSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'")
        response.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.setdefault('Referrer-Policy', 'same-origin')
        return response

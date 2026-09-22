from datetime import timedelta
from ipaddress import ip_address
from math import ceil
from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import AuthenticationBucket


def client_address(request):
    address = request.META.get('REMOTE_ADDR', '')
    if address in settings.AUTH_TRUSTED_PROXIES:
        address = request.META.get('HTTP_X_REAL_IP', address)
    try:
        return str(ip_address(address))
    except ValueError:
        return 'unknown'


def counter_key(kind, address, identity=''):
    value = f'{kind}\x00{address}\x00{identity.strip().casefold()[:254]}'
    return salted_hmac('school-auth-throttle', value, algorithm='sha256').hexdigest()


def login_keys(request, username):
    address = client_address(request)
    return [(counter_key('login-user', address, username), settings.LOGIN_FAILURE_LIMIT), (counter_key('login-ip', address), settings.AUTH_IP_FAILURE_LIMIT)]


def reset_keys(request):
    return [(counter_key('reset-ip', client_address(request)), settings.RESET_REQUEST_LIMIT)]


def blocked_for(keys):
    now = timezone.now()
    cutoff = now - timedelta(seconds=settings.AUTH_WINDOW_SECONDS)
    limits = dict(keys)
    wait = 0
    for bucket in AuthenticationBucket.objects.filter(key__in=limits, window_started__gt=cutoff):
        if bucket.attempts >= limits[bucket.key]:
            wait = max(wait, ceil((bucket.window_started + timedelta(seconds=settings.AUTH_WINDOW_SECONDS) - now).total_seconds()))
    return wait


@transaction.atomic
def record_attempt(keys):
    now = timezone.now()
    cutoff = now - timedelta(seconds=settings.AUTH_WINDOW_SECONDS)
    # Consistent key order avoids deadlocks when simultaneous requests share the IP bucket.
    for key, _ in sorted(keys):
        bucket, _ = AuthenticationBucket.objects.get_or_create(key=key, defaults={'window_started': now})
        bucket = AuthenticationBucket.objects.select_for_update().get(pk=key)
        if bucket.window_started <= cutoff:
            bucket.window_started, bucket.attempts = now, 0
        bucket.attempts += 1
        bucket.save(update_fields=['attempts', 'window_started'])


@receiver(user_login_failed, dispatch_uid='school.failed_login_counter')
def failed_login(sender, credentials, request=None, **kwargs):
    if request is not None:
        record_attempt(login_keys(request, credentials.get('username', '')))


@receiver(user_logged_in, dispatch_uid='school.clear_login_counter')
def successful_login(sender, request, user, **kwargs):
    if request is not None:
        key = login_keys(request, user.username)[0][0]
        AuthenticationBucket.objects.filter(pk=key).delete()


class ThrottledModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if request is not None and blocked_for(login_keys(request, username or '')):
            raise PermissionDenied
        return super().authenticate(request, username=username, password=password, **kwargs)

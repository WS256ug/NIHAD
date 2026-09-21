from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@login_required
@never_cache
@require_GET
def home(request):
    return render(request, "dashboard/home.html")

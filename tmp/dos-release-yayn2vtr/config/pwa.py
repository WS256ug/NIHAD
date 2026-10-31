from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.schools.models import School


@never_cache
@require_GET
def manifest(request):
    return JsonResponse({
        "id": reverse("dashboard:home"),
        "name": School.objects.values_list("name", flat=True).first() or "NIHAD School",
        "short_name": "NIHAD",
        "start_url": reverse("dashboard:home"),
        "scope": reverse("dashboard:home"),
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#701c35",
        "prefer_related_applications": False,
        "icons": [
            {"src": static(f"img/pwa-{size}.png"), "sizes": f"{size}x{size}",
             "type": "image/png", "purpose": "any"}
            for size in (192, 512)
        ],
    }, content_type="application/manifest+json")


@never_cache
@require_GET
def service_worker(request):
    # Render without request context: this public script must never contain user data.
    offline_html = render_to_string("pwa/offline.html")
    response = HttpResponse(
        render_to_string("pwa/service-worker.js", {"offline_html": offline_html}),
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = reverse("dashboard:home")
    return response

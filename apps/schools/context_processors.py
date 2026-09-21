from .models import School


def school_identity(request):
    name = School.objects.values_list("name", flat=True).first()
    return {"school_display_name": name or "NIHAD School"}

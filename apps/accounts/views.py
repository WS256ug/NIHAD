from django.contrib.auth.views import LoginView
from django.http import HttpResponse


class SignInView(LoginView):
    template_name = "registration/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get("HX-Request") == "true":
            # Reload after authentication so the browser receives the rotated CSRF token.
            return HttpResponse(headers={"HX-Redirect": response.url})
        return response

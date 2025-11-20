from django.urls import path

from .views import CodeQAView, HealthView

urlpatterns = [
    path("code-qa/", CodeQAView.as_view(), name="code-qa"),
    path("code-qa/health/", HealthView.as_view(), name="code-qa-health"),
]

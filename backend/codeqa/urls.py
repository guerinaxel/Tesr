from django.urls import path

from .views import (
    BuildRagIndexView,
    CodeQAView,
    CodeQAStreamView,
    DocumentAnalysisView,
    HealthView,
    SearchView,
    TopicDetailView,
    TopicListView,
)

urlpatterns = [
    path("code-qa/", CodeQAView.as_view(), name="code-qa"),
    path("code-qa/stream/", CodeQAStreamView.as_view(), name="code-qa-stream"),
    path("code-qa/health/", HealthView.as_view(), name="code-qa-health"),
    path("document-qa/", DocumentAnalysisView.as_view(), name="document-qa"),
    path("code-qa/build-rag/", BuildRagIndexView.as_view(), name="code-qa-build-rag"),
    path("topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
    path("search/", SearchView.as_view(), name="search"),
]

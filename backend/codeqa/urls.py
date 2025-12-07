from django.urls import path

from .views import (
    BuildRagIndexView,
    CodeQAView,
    CodeQAStreamView,
    DocumentAnalysisView,
    HealthView,
    RagSourceBuildView,
    RagSourceDetailView,
    RagSourceListView,
    RagSourceRebuildView,
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
    path("rag-sources/", RagSourceListView.as_view(), name="rag-source-list"),
    path("rag-sources/build/", RagSourceBuildView.as_view(), name="rag-source-build"),
    path("rag-sources/<uuid:source_id>/", RagSourceDetailView.as_view(), name="rag-source-detail"),
    path(
        "rag-sources/<uuid:source_id>/rebuild/",
        RagSourceRebuildView.as_view(),
        name="rag-source-rebuild",
    ),
    path("topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
    path("search/", SearchView.as_view(), name="search"),
]

from __future__ import annotations

import uuid

from django.db import models


class Topic(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:  # pragma: no cover - string representation
        return self.name


class Message(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"

    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    ]

    topic = models.ForeignKey(Topic, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:  # pragma: no cover - string representation
        return f"{self.role}: {self.content[:20]}"


class RagSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    path = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    total_files = models.PositiveIntegerField(default=0)
    total_chunks = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "name"]

    def __str__(self) -> str:  # pragma: no cover - string representation
        return self.name

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


MessageRole = Literal["user", "assistant"]


@dataclass
class Message:
    role: MessageRole
    content: str


@dataclass
class Topic:
    id: int
    name: str
    messages: list[Message] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "message_count": len(self.messages),
            "messages": [
                {"role": message.role, "content": message.content}
                for message in self.messages
            ],
        }


class TopicStore:
    """In-memory storage for chat topics and their message history."""

    def __init__(self) -> None:
        self._topics: dict[int, Topic] = {}
        self._next_id = 1

    def reset(self) -> None:
        self._topics.clear()
        self._next_id = 1

    def create_topic(self, name: str) -> Topic:
        topic = Topic(id=self._next_id, name=name.strip())
        self._topics[topic.id] = topic
        self._next_id += 1
        return topic

    def list_topics(self) -> list[dict]:
        return [self._serialize_topic_metadata(topic) for topic in self._topics.values()]

    def get_topic(self, topic_id: int) -> Topic | None:
        return self._topics.get(topic_id)

    def add_exchange(self, topic_id: int, question: str, answer: str) -> Topic:
        topic = self._topics.get(topic_id)
        if topic is None:
            raise KeyError(f"Topic {topic_id} not found")

        topic.messages.extend(
            [
                Message(role="user", content=question),
                Message(role="assistant", content=answer),
            ]
        )
        return topic

    def serialize_topic(self, topic_id: int) -> dict | None:
        topic = self._topics.get(topic_id)
        return topic.to_dict() if topic else None

    @staticmethod
    def _serialize_topic_metadata(topic: Topic) -> dict:
        return {
            "id": topic.id,
            "name": topic.name,
            "message_count": len(topic.messages),
        }


topic_store = TopicStore()


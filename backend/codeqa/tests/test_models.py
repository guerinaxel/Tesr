from __future__ import annotations

from django.test import SimpleTestCase

from codeqa.models import Message, Topic


class ModelStrTests(SimpleTestCase):
    def test_topic_and_message_str(self) -> None:
        # Arrange
        topic = Topic(name="Demo")
        message = Message(topic=topic, role=Message.ROLE_USER, content="Hello world")

        # Act
        topic_repr = str(topic)
        message_repr = str(message)

        # Assert
        self.assertIn("Demo", topic_repr)
        self.assertIn("user", message_repr)

from django.test import TestCase

from codeqa.models import Message, Topic


class ModelTests(TestCase):
    def test_topic_str_and_ordering(self) -> None:
        # Arrange
        older = Topic.objects.create(name="Older")
        newer = Topic.objects.create(name="Newer")

        # Act
        topics = list(Topic.objects.all())

        # Assert
        self.assertEqual("Newer", str(newer))
        self.assertEqual([newer, older], topics)

    def test_message_str_and_ordering(self) -> None:
        # Arrange
        topic = Topic.objects.create(name="Thread")
        first = Message.objects.create(topic=topic, role=Message.ROLE_USER, content="First question")
        second = Message.objects.create(
            topic=topic, role=Message.ROLE_ASSISTANT, content="Second answer"
        )

        # Act
        messages = list(topic.messages.all())

        # Assert
        self.assertTrue(str(first).startswith("user"))
        self.assertEqual([first, second], messages)

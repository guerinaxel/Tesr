from django.test import TestCase

from codeqa.models import Message, Topic


class ModelTests(TestCase):
    def test_topic_str_and_ordering(self) -> None:
        older = Topic.objects.create(name="Older")
        newer = Topic.objects.create(name="Newer")

        self.assertEqual("Newer", str(newer))
        self.assertEqual([newer, older], list(Topic.objects.all()))

    def test_message_str_and_ordering(self) -> None:
        topic = Topic.objects.create(name="Thread")
        first = Message.objects.create(topic=topic, role=Message.ROLE_USER, content="First question")
        second = Message.objects.create(
            topic=topic, role=Message.ROLE_ASSISTANT, content="Second answer"
        )

        self.assertTrue(str(first).startswith("user"))
        self.assertEqual([first, second], list(topic.messages.all()))

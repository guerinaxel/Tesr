from __future__ import annotations

from django.test import SimpleTestCase

from codeqa.serializers import CodeQuestionSerializer


class CodeQuestionSerializerTests(SimpleTestCase):
    def test_valid_payload_with_defaults(self) -> None:
        serializer = CodeQuestionSerializer(data={"question": "What is RAG?"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(5, serializer.validated_data["top_k"])

    def test_rejects_blank_question(self) -> None:
        serializer = CodeQuestionSerializer(data={"question": "   "})
        self.assertFalse(serializer.is_valid())
        self.assertIn("question", serializer.errors)

    def test_limits_top_k_range(self) -> None:
        serializer = CodeQuestionSerializer(data={"question": "ok", "top_k": 25})
        self.assertFalse(serializer.is_valid())
        self.assertIn("top_k", serializer.errors)

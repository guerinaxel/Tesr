from __future__ import annotations

from django.test import SimpleTestCase

from codeqa.serializers import CodeQuestionSerializer


class CodeQuestionSerializerTests(SimpleTestCase):
    def test_valid_payload_with_defaults(self) -> None:
        # Arrange
        serializer = CodeQuestionSerializer(data={"question": "What is RAG?"})

        # Act
        is_valid = serializer.is_valid()

        # Assert
        self.assertTrue(is_valid, serializer.errors)
        self.assertEqual(5, serializer.validated_data["top_k"])
        self.assertEqual(0.5, serializer.validated_data["fusion_weight"])

    def test_rejects_blank_question(self) -> None:
        # Arrange
        serializer = CodeQuestionSerializer(data={"question": "   "})

        # Act
        is_valid = serializer.is_valid()

        # Assert
        self.assertFalse(is_valid)
        self.assertIn("question", serializer.errors)

    def test_limits_top_k_range(self) -> None:
        # Arrange
        serializer = CodeQuestionSerializer(data={"question": "ok", "top_k": 25})

        # Act
        is_valid = serializer.is_valid()

        # Assert
        self.assertFalse(is_valid)
        self.assertIn("top_k", serializer.errors)

    def test_limits_fusion_weight_range(self) -> None:
        # Arrange
        serializer = CodeQuestionSerializer(
            data={"question": "ok", "fusion_weight": 1.5}
        )

        # Act
        is_valid = serializer.is_valid()

        # Assert
        self.assertFalse(is_valid)
        self.assertIn("fusion_weight", serializer.errors)

    def test_rejects_invalid_topic_id(self) -> None:
        # Arrange
        serializer = CodeQuestionSerializer(data={"question": "ok", "topic_id": 0})

        # Act
        is_valid = serializer.is_valid()

        # Assert
        self.assertFalse(is_valid)
        self.assertIn("topic_id", serializer.errors)

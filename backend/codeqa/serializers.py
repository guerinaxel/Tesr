from rest_framework import serializers


class CodeQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=2000,
        allow_blank=False,
        trim_whitespace=True,
    )
    top_k = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        default=5,
    )


class BuildRagRequestSerializer(serializers.Serializer):
    root = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
        help_text="Optional filesystem path to use as project root when building the RAG index.",
    )

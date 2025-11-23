from rest_framework import serializers


class CodeQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=2000,
        allow_blank=False,
        trim_whitespace=True,
    )
    system_prompt = serializers.ChoiceField(
        choices=(
            ("code expert", "code expert"),
            ("document expert", "document expert"),
            ("custom", "custom"),
        ),
        default="code expert",
    )
    custom_prompt = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
        write_only=True,
    )
    custom_pront = serializers.CharField(  # Backwards compatible typo handling
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
        write_only=True,
    )
    top_k = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        default=5,
    )
    fusion_weight = serializers.FloatField(
        required=False,
        min_value=0.0,
        max_value=1.0,
        default=0.5,
    )
    topic_id = serializers.IntegerField(
        required=False,
        min_value=1,
        allow_null=True,
        default=None,
    )

    def validate(self, attrs: dict) -> dict:
        system_prompt = attrs.get("system_prompt")
        custom_prompt = attrs.get("custom_prompt")
        typo_prompt = attrs.get("custom_pront")

        if system_prompt == "custom":
            merged_prompt = custom_prompt or typo_prompt
            if not merged_prompt or not str(merged_prompt).strip():
                raise serializers.ValidationError(
                    {"custom_prompt": "A custom prompt is required when system_prompt is 'custom'."}
                )
            attrs["custom_prompt"] = str(merged_prompt).strip()
        elif custom_prompt:
            attrs["custom_prompt"] = custom_prompt.strip()

        return attrs


class TopicCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=200,
        allow_blank=False,
        trim_whitespace=True,
    )


class BuildRagRequestSerializer(serializers.Serializer):
    root = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
        help_text="Optional filesystem path to use as project root when building the RAG index.",
    )

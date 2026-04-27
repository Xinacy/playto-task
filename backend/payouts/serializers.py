from rest_framework import serializers
from .models import Credit, IdempotencyKey, Merchant, Payout


class MerchantSerializer(serializers.ModelSerializer):
    balance_paise = serializers.IntegerField(read_only=True)
    held_balance_paise = serializers.IntegerField(read_only=True)

    class Meta:
        model = Merchant
        fields = [
            "id",
            "user",
            "balance_paise",
            "held_balance_paise",
            "created_at",
            "updated_at",
        ]


class CreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credit
        fields = ["id", "amount_paise", "description", "created_at"]


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            "id",
            "amount_paise",
            "bank_account_id",
            "status",
            "created_at",
            "updated_at",
            "processing_started_at",
            "attempts",
            "error_message",
        ]


class PayoutRequestSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.CharField(max_length=255)

    def validate_amount_paise(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value


class IdempotencyKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = IdempotencyKey
        fields = ["key", "merchant", "response_data", "created_at", "expires_at"]

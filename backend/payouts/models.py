from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
import uuid


class Merchant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance_paise = models.BigIntegerField(default=0)
    held_balance_paise = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance_paise__gte=0),
                name="merchant_balance_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(held_balance_paise__gte=0),
                name="merchant_held_balance_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(balance_paise__gte=models.F("held_balance_paise")),
                name="merchant_balance_covers_holds",
            ),
        ]

    def __str__(self):
        return f"Merchant {self.user.username}"


class Credit(models.Model):
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="credits"
    )
    amount_paise = models.BigIntegerField()
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_paise__gt=0),
                name="credit_amount_positive",
            )
        ]

    def __str__(self):
        return f"Credit {self.amount_paise} paise for {self.merchant}"


class Payout(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="payouts"
    )
    amount_paise = models.BigIntegerField()
    bank_account_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    idempotency_key = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_paise__gt=0),
                name="payout_amount_positive",
            )
        ]
        indexes = [
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Payout {self.id} - {self.amount_paise} paise"

    def clean(self):
        if not self.pk:
            return
        old_status = Payout.objects.filter(pk=self.pk).values_list("status", flat=True).first()
        if old_status and self.status != old_status:
            legal_transitions = {
                "pending": {"processing"},
                "processing": {"completed", "failed"},
                "completed": set(),
                "failed": set(),
            }
            if self.status not in legal_transitions[old_status]:
                raise ValidationError(
                    {"status": f"Illegal payout transition {old_status} -> {self.status}"}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, db_index=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    response_data = models.JSONField()
    response_status = models.PositiveSmallIntegerField(default=201)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "key"], name="unique_idempotency_key_per_merchant"
            )
        ]

    def __str__(self):
        return f"IdempotencyKey {self.key}"

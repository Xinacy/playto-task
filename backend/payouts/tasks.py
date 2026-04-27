import random
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from datetime import timedelta
from .models import Merchant, Payout


@shared_task
def process_pending_payouts():
    """Process pending payouts that are ready for processing."""
    with transaction.atomic():
        pending_ids = list(
            Payout.objects.select_for_update(skip_locked=True)
            .filter(status="pending")
            .order_by("created_at")
            .values_list("id", flat=True)[:10]
        )

    for payout_id in pending_ids:
        process_payout.delay(str(payout_id))


@shared_task
def process_payout(payout_id):
    """Process a single payout with simulation of bank settlement."""
    with transaction.atomic():
        try:
            payout = Payout.objects.select_for_update().get(id=payout_id)
        except Payout.DoesNotExist:
            return

        if payout.status not in {"pending", "processing"}:
            return

        if payout.status == "pending":
            payout.status = "processing"
        payout.processing_started_at = timezone.now()
        payout.attempts += 1
        payout.save(
            update_fields=["status", "processing_started_at", "attempts", "updated_at"]
        )

    random_outcome = random.random()

    if random_outcome < 0.7:  # 70% success
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status != "processing":
                return
            payout.status = "completed"
            payout.error_message = ""
            payout.save(update_fields=["status", "error_message", "updated_at"])
            merchant = Merchant.objects.select_for_update().get(id=payout.merchant_id)
            Merchant.objects.filter(id=merchant.id).update(
                balance_paise=F("balance_paise") - payout.amount_paise,
                held_balance_paise=F("held_balance_paise") - payout.amount_paise,
            )

    elif random_outcome < 0.9:  # 20% failure
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status != "processing":
                return
            payout.status = "failed"
            payout.error_message = "Bank settlement failed"
            payout.save(update_fields=["status", "error_message", "updated_at"])
            merchant = Merchant.objects.select_for_update().get(id=payout.merchant_id)
            Merchant.objects.filter(id=merchant.id).update(
                held_balance_paise=F("held_balance_paise") - payout.amount_paise,
            )

    else:  # 10% hang in processing
        pass


@shared_task
def retry_processing_payouts():
    """Retry payouts stuck in processing for more than 30 seconds."""
    now = timezone.now()

    with transaction.atomic():
        stuck_payouts = list(
            Payout.objects.select_for_update(skip_locked=True)
            .filter(
                status="processing",
                processing_started_at__lt=now - timedelta(seconds=30),
            )
            .order_by("processing_started_at")[:25]
        )

    for payout in stuck_payouts:
        backoff_seconds = 30 * (2 ** max(payout.attempts - 1, 0))
        if payout.processing_started_at > now - timedelta(seconds=backoff_seconds):
            continue

        if payout.attempts >= 3:
            with transaction.atomic():
                payout = Payout.objects.select_for_update().get(id=payout.id)
                if payout.status != "processing":
                    continue
                payout.status = "failed"
                payout.error_message = "Max retry attempts reached"
                payout.save(update_fields=["status", "error_message", "updated_at"])
                merchant = Merchant.objects.select_for_update().get(
                    id=payout.merchant_id
                )
                Merchant.objects.filter(id=merchant.id).update(
                    held_balance_paise=F("held_balance_paise") - payout.amount_paise,
                )
        else:
            process_payout.delay(str(payout.id))

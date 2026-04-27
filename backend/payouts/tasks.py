import random
import time
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .models import Payout, Merchant


@shared_task
def process_pending_payouts():
    """Process pending payouts that are ready for processing."""
    now = timezone.now()

    # Find pending payouts that haven't been processed yet
    pending_payouts = Payout.objects.filter(status="pending").select_for_update(
        skip_locked=True
    )[:10]

    for payout in pending_payouts:
        process_payout.delay(payout.id)


@shared_task
def process_payout(payout_id):
    """Process a single payout with simulation of bank settlement."""
    try:
        payout = Payout.objects.select_for_update().get(id=payout_id)
    except Payout.DoesNotExist:
        return

    # Only process if still pending
    if payout.status != "pending":
        return

    # Move to processing state
    payout.status = "processing"
    payout.processing_started_at = timezone.now()
    payout.attempts += 1
    payout.save()

    # Simulate bank settlement with random outcome
    random_outcome = random.random()

    if random_outcome < 0.7:  # 70% success
        # Success - mark as completed
        payout.status = "completed"
        payout.save()

        # Release held funds (they stay with merchant since payout succeeded)
        with transaction.atomic():
            merchant = Merchant.objects.select_for_update().get(id=payout.merchant_id)
            merchant.held_balance_paise -= payout.amount_paise
            merchant.save()

    elif random_outcome < 0.9:  # 20% failure
        # Failure - mark as failed and return funds
        payout.status = "failed"
        payout.error_message = "Bank settlement failed"
        payout.save()

        # Return held funds to merchant balance
        with transaction.atomic():
            merchant = Merchant.objects.select_for_update().get(id=payout.merchant_id)
            merchant.held_balance_paise -= payout.amount_paise
            merchant.balance_paise -= (
                payout.amount_paise
            )  # Remove from balance since payout failed
            merchant.save()

    else:  # 10% hang in processing
        # Leave in processing state - will be retried by retry processor
        pass


@shared_task
def retry_processing_payouts():
    """Retry payouts stuck in processing for more than 30 seconds."""
    now = timezone.now()
    cutoff_time = now - timedelta(seconds=30)

    # Find payouts stuck in processing for too long
    stuck_payouts = Payout.objects.filter(
        status="processing",
        processing_started_at__lt=cutoff_time,
        attempts__lt=3,  # Max 3 attempts
    ).select_for_update(skip_locked=True)

    for payout in stuck_payouts:
        # Reset to pending to be retried
        payout.status = "pending"
        payout.processing_started_at = None
        payout.save()

        # If max attempts reached, mark as failed
        if payout.attempts >= 3:
            payout.status = "failed"
            payout.error_message = "Max retry attempts reached"
            payout.save()

            # Return held funds
            with transaction.atomic():
                merchant = Merchant.objects.select_for_update().get(
                    id=payout.merchant_id
                )
                merchant.held_balance_paise -= payout.amount_paise
                merchant.balance_paise -= payout.amount_paise
                merchant.save()

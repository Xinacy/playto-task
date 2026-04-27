from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import close_old_connections, connections
from django.test import Client, TransactionTestCase
from django.utils import timezone

from payouts.models import Credit, Merchant, Payout
from payouts.tasks import process_payout, retry_processing_payouts


class PayoutIntegrityTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(username="merchant1", password="password")
        self.merchant = Merchant.objects.create(
            user=self.user, balance_paise=10000, held_balance_paise=0
        )
        Credit.objects.create(
            merchant=self.merchant,
            amount_paise=10000,
            description="Customer payment",
        )

    def post_payout(self, amount_paise, key=None):
        client = Client()
        return client.post(
            "/api/v1/payouts",
            data={"amount_paise": amount_paise, "bank_account_id": "bank_123"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key or str(uuid4()),
        )

    def test_idempotency_returns_same_response_without_duplicate_payout(self):
        key = str(uuid4())

        first = self.post_payout(2500, key)
        second = self.post_payout(2500, key)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(Payout.objects.filter(merchant=self.merchant).count(), 1)

    def test_concurrent_payouts_only_hold_available_funds_once(self):
        def request_payout():
            close_old_connections()
            try:
                return self.post_payout(6000).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda _: request_payout(), range(2)))

        self.merchant.refresh_from_db()
        self.assertEqual(statuses.count(201), 1)
        self.assertEqual(statuses.count(400), 1)
        self.assertEqual(self.merchant.balance_paise, 10000)
        self.assertEqual(self.merchant.held_balance_paise, 6000)

    @patch("payouts.tasks.random.random", return_value=0.1)
    def test_successful_payout_debits_total_and_held_atomically(self, _random):
        payout = Payout.objects.create(
            merchant=self.merchant,
            amount_paise=4000,
            bank_account_id="bank_123",
            idempotency_key=str(uuid4()),
        )
        Merchant.objects.filter(id=self.merchant.id).update(held_balance_paise=4000)

        process_payout(str(payout.id))

        payout.refresh_from_db()
        self.merchant.refresh_from_db()
        self.assertEqual(payout.status, "completed")
        self.assertEqual(self.merchant.balance_paise, 6000)
        self.assertEqual(self.merchant.held_balance_paise, 0)

    @patch("payouts.tasks.random.random", return_value=0.8)
    def test_failed_payout_releases_hold_without_debiting_total(self, _random):
        payout = Payout.objects.create(
            merchant=self.merchant,
            amount_paise=4000,
            bank_account_id="bank_123",
            idempotency_key=str(uuid4()),
        )
        Merchant.objects.filter(id=self.merchant.id).update(held_balance_paise=4000)

        process_payout(str(payout.id))

        payout.refresh_from_db()
        self.merchant.refresh_from_db()
        self.assertEqual(payout.status, "failed")
        self.assertEqual(self.merchant.balance_paise, 10000)
        self.assertEqual(self.merchant.held_balance_paise, 0)

    def test_stuck_processing_payout_fails_after_max_attempts_and_releases_hold(self):
        payout = Payout.objects.create(
            merchant=self.merchant,
            amount_paise=4000,
            bank_account_id="bank_123",
            idempotency_key=str(uuid4()),
        )
        payout.status = "processing"
        payout.attempts = 3
        payout.processing_started_at = timezone.now() - timedelta(minutes=5)
        payout.save()
        Merchant.objects.filter(id=self.merchant.id).update(held_balance_paise=4000)

        retry_processing_payouts()

        payout.refresh_from_db()
        self.merchant.refresh_from_db()
        self.assertEqual(payout.status, "failed")
        self.assertEqual(self.merchant.held_balance_paise, 0)

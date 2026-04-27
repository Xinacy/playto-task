import os
import django
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "playto.settings")
django.setup()

from payouts.models import Merchant, Payout, IdempotencyKey
from django.contrib.auth.models import User


def test_concurrent_payouts():
    """Test concurrent payout requests to ensure only one succeeds."""
    print("Testing concurrent payouts...")

    # Get a merchant
    merchant = Merchant.objects.first()
    if not merchant:
        print("No merchants found. Run seed_data first.")
        return

    initial_balance = merchant.balance_paise
    initial_held = merchant.held_balance_paise

    print(f"Merchant: {merchant.user.username}")
    print(f"Initial balance: {initial_balance} paise")
    print(f"Initial held: {initial_held} paise")

    # Create 10 concurrent payout requests for 60% of balance
    amount = int(initial_balance * 0.6)
    num_requests = 10
    idempotency_key = f"test-concurrent-{int(time.time())}"

    def make_payout_request(key):
        try:
            response = requests.post(
                "http://localhost:8000/api/v1/payouts",
                json={"amount_paise": amount, "bank_account_id": "test-account-123"},
                headers={
                    "Idempotency-Key": f"{key}-{idempotency_key}",
                    "Authorization": "Bearer demo-token",
                },
            )
            return response.status_code, response.json()
        except Exception as e:
            return None, str(e)

    # Execute concurrent requests
    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(make_payout_request, i) for i in range(num_requests)]
        results = []
        for future in as_completed(futures):
            results.append(future.result())

    # Analyze results
    successful = [r for r in results if r[0] == 201]
    failed = [r for r in results if r[0] != 201]

    print(f"\nResults:")
    print(f"Successful requests: {len(successful)}")
    print(f"Failed requests: {len(failed)}")

    # Check database state
    merchant.refresh_from_db()
    payouts = Payout.objects.filter(
        merchant=merchant, idempotency_key__icontains=idempotency_key
    )

    print(f"\nDatabase state:")
    print(f"Final balance: {merchant.balance_paise} paise")
    print(f"Final held: {merchant.held_balance_paise} paise")
    print(f"Total payouts created: {payouts.count()}")

    # Verify only one payout was created
    if payouts.count() == 1:
        print("✓ PASS: Only one payout created")
    else:
        print(f"✗ FAIL: Expected 1 payout, got {payouts.count()}")

    # Verify balance integrity
    expected_held = amount if payouts.count() == 1 else 0
    if merchant.held_balance_paise == expected_held:
        print("✓ PASS: Balance integrity maintained")
    else:
        print(
            f"✗ FAIL: Expected held balance {expected_held}, got {merchant.held_balance_paise}"
        )


def test_idempotency():
    """Test idempotency with same key."""
    print("\nTesting idempotency...")

    merchant = Merchant.objects.first()
    if not merchant:
        print("No merchants found.")
        return

    amount = 10000  # 100 INR
    idempotency_key = f"test-idempotency-{int(time.time())}"

    # Make same request twice
    responses = []
    for i in range(2):
        try:
            response = requests.post(
                "http://localhost:8000/api/v1/payouts",
                json={"amount_paise": amount, "bank_account_id": "test-account-456"},
                headers={
                    "Idempotency-Key": idempotency_key,
                    "Authorization": "Bearer demo-token",
                },
            )
            responses.append((response.status_code, response.json()))
        except Exception as e:
            responses.append((None, str(e)))

    print(f"First request: {responses[0][0]}")
    print(f"Second request: {responses[1][0]}")

    # Both should succeed with same response
    if responses[0][0] == 201 and responses[1][0] == 200:
        print("✓ PASS: Idempotency working correctly")
    else:
        print("✗ FAIL: Idempotency not working")

    # Check database
    payouts = Payout.objects.filter(idempotency_key=idempotency_key)
    print(f"Payouts created: {payouts.count()}")

    if payouts.count() == 1:
        print("✓ PASS: Only one payout created in database")
    else:
        print(f"✗ FAIL: Expected 1 payout, got {payouts.count()}")


def test_insufficient_balance():
    """Test that insufficient balance is rejected."""
    print("\nTesting insufficient balance...")

    merchant = Merchant.objects.first()
    if not merchant:
        print("No merchants found.")
        return

    # Request more than available balance
    amount = merchant.balance_paise + 10000
    idempotency_key = f"test-insufficient-{int(time.time())}"

    try:
        response = requests.post(
            "http://localhost:8000/api/v1/payouts",
            json={"amount_paise": amount, "bank_account_id": "test-account-789"},
            headers={
                "Idempotency-Key": idempotency_key,
                "Authorization": "Bearer demo-token",
            },
        )

        if response.status_code == 400:
            print("✓ PASS: Insufficient balance rejected")
        else:
            print(f"✗ FAIL: Expected 400, got {response.status_code}")
    except Exception as e:
        print(f"✗ FAIL: Request failed: {e}")


if __name__ == "__main__":
    print("Starting concurrency tests...")
    print("=" * 50)

    test_concurrent_payouts()
    test_idempotency()
    test_insufficient_balance()

    print("\n" + "=" * 50)
    print("Tests completed")

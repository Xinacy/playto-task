# Explainer

## 1. The Ledger

Balance query from `backend/payouts/views.py`:

```python
merchant = Merchant.objects.annotate(
    available_balance=F("balance_paise") - F("held_balance_paise")
).get(id=get_request_merchant(request).id)

credit_total = merchant.credits.aggregate(total=Coalesce(Sum("amount_paise"), 0))[
    "total"
]
completed_payout_total = merchant.payouts.filter(status="completed").aggregate(
    total=Coalesce(Sum("amount_paise"), 0)
)["total"]
```

Credits increase `balance_paise`. A payout first increases `held_balance_paise`, so available balance drops immediately. Only a completed payout decreases total `balance_paise`; a failed payout only releases the hold. This avoids treating pending payouts as settled debits while still preventing double spend.

## 2. The Lock

Exact overdraft prevention code from `backend/payouts/views.py`:

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant.id)

    held = Merchant.objects.filter(
        id=merchant.id,
        balance_paise__gte=F("held_balance_paise") + amount_paise,
    ).update(held_balance_paise=F("held_balance_paise") + amount_paise)
    if held != 1:
        return Response(
            {"error": "Insufficient available balance"},
            status=status.HTTP_400_BAD_REQUEST,
        )
```

It relies on Postgres row-level locks via `SELECT ... FOR UPDATE`, plus an atomic conditional `UPDATE`. Concurrent requests serialize on the merchant row, and the `balance_paise >= held_balance_paise + amount` predicate is checked inside the database at update time.

## 3. The Idempotency

The system stores each seen key in `IdempotencyKey` with a unique constraint on `(merchant, key)`:

```python
models.UniqueConstraint(
    fields=["merchant", "key"], name="unique_idempotency_key_per_merchant"
)
```

On request, it locks the merchant, then locks and checks any existing non-expired key:

```python
existing_key = (
    IdempotencyKey.objects.select_for_update()
    .filter(
        key=idempotency_key,
        merchant=merchant,
        expires_at__gt=timezone.now(),
    )
    .first()
)
if existing_key:
    return Response(
        existing_key.response_data, status=existing_key.response_status
    )
```

If the first request is still in flight, the second request waits on the same merchant row lock. After the first commits the payout and idempotency row, the second enters the transaction, finds the saved key, and returns the original response without creating another payout.

## 4. The State Machine

Blocked in `backend/payouts/models.py`:

```python
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
```

Because `failed` maps to an empty set, `failed -> completed` is rejected during `full_clean()` before save.

## 5. The AI Audit

Subtly wrong AI version:

```python
available = merchant.balance_paise - merchant.held_balance_paise
if available < amount_paise:
    return Response({"error": "Insufficient available balance"}, status=400)

merchant.held_balance_paise += amount_paise
merchant.save()
```

Problem caught: two concurrent requests can both read the same available balance before either saves, so both can pass the check and over-hold the merchant balance.

Replaced with:

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant.id)
    held = Merchant.objects.filter(
        id=merchant.id,
        balance_paise__gte=F("held_balance_paise") + amount_paise,
    ).update(held_balance_paise=F("held_balance_paise") + amount_paise)
    if held != 1:
        return Response(
            {"error": "Insufficient available balance"},
            status=status.HTTP_400_BAD_REQUEST,
        )
```

This makes the check and hold happen under a database transaction and row lock.

## Note on AI Usage

I used AI to write the README and this explainer as well, because it just looks beautiful. Writing Markdown is hard for me since I do not know the syntax well, so I gave my answers to AI and asked it to write them in markdown syntax.

I also used AI for 100% of the frontend. To be honest, this task was more focused on the backend, and the design is not what is being judged, so it made no sense to put effort into designing the frontend manually.

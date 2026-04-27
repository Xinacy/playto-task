from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Merchant, Payout, IdempotencyKey
from .serializers import PayoutSerializer, PayoutRequestSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_payout(request):
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return Response(
            {"error": "Idempotency-Key header is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        merchant = Merchant.objects.get(user=request.user)
    except Merchant.DoesNotExist:
        return Response(
            {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
        )

    # Check for existing idempotency key
    try:
        existing_key = IdempotencyKey.objects.get(
            key=idempotency_key, merchant=merchant, expires_at__gt=timezone.now()
        )
        return Response(existing_key.response_data, status=status.HTTP_200_OK)
    except IdempotencyKey.DoesNotExist:
        pass

    serializer = PayoutRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount_paise = serializer.validated_data["amount_paise"]
    bank_account_id = serializer.validated_data["bank_account_id"]

    # Use database-level locking to prevent race conditions
    with transaction.atomic():
        # Lock the merchant row for update
        merchant = Merchant.objects.select_for_update().get(id=merchant.id)

        # Check if merchant has sufficient available balance (balance - held)
        available_balance = merchant.balance_paise - merchant.held_balance_paise
        if available_balance < amount_paise:
            return Response(
                {"error": "Insufficient available balance"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Hold the funds
        merchant.held_balance_paise += amount_paise
        merchant.save()

        # Create the payout
        payout = Payout.objects.create(
            merchant=merchant,
            amount_paise=amount_paise,
            bank_account_id=bank_account_id,
            idempotency_key=idempotency_key,
            status="pending",
        )

        # Store the idempotency key response
        response_data = PayoutSerializer(payout).data
        expires_at = timezone.now() + timedelta(hours=24)
        IdempotencyKey.objects.create(
            key=idempotency_key,
            merchant=merchant,
            response_data=response_data,
            expires_at=expires_at,
        )

        return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payout_history(request):
    try:
        merchant = Merchant.objects.get(user=request.user)
    except Merchant.DoesNotExist:
        return Response(
            {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
        )

    payouts = Payout.objects.filter(merchant=merchant).order_by("-created_at")
    serializer = PayoutSerializer(payouts, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def merchant_dashboard(request):
    try:
        merchant = Merchant.objects.get(user=request.user)
    except Merchant.DoesNotExist:
        return Response(
            {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
        )

    recent_credits = merchant.credits.order_by("-created_at")[:10]
    recent_debits = merchant.payouts.exclude(status="pending").order_by("-created_at")[
        :10
    ]

    from .serializers import CreditSerializer

    return Response(
        {
            "available_balance_paise": merchant.balance_paise
            - merchant.held_balance_paise,
            "held_balance_paise": merchant.held_balance_paise,
            "total_balance_paise": merchant.balance_paise,
            "recent_credits": CreditSerializer(recent_credits, many=True).data,
            "recent_debits": PayoutSerializer(recent_debits, many=True).data,
        }
    )

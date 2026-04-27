from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from .models import Merchant, Payout, IdempotencyKey
from .serializers import CreditSerializer, PayoutSerializer, PayoutRequestSerializer


@api_view(["GET"])
@permission_classes([])
def merchant_list(request):
    merchants = (
        Merchant.objects.select_related("user")
        .annotate(available_balance=F("balance_paise") - F("held_balance_paise"))
        .order_by("user__username")
    )
    return Response(
        [
            {
                "id": merchant.id,
                "username": merchant.user.username,
                "email": merchant.user.email,
                "available_balance_paise": merchant.available_balance,
                "held_balance_paise": merchant.held_balance_paise,
                "total_balance_paise": merchant.balance_paise,
            }
            for merchant in merchants
        ]
    )


def get_request_merchant(request):
    if request.user.is_authenticated:
        return Merchant.objects.get(user=request.user)

    username = (
        request.headers.get("X-Merchant-Username")
        or request.GET.get("merchant")
        or "merchant1"
    )
    user = User.objects.get(username=username)
    return Merchant.objects.get(user=user)


@api_view(["POST"])
@permission_classes([])
def create_payout(request):
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return Response(
            {"error": "Idempotency-Key header is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        merchant = get_request_merchant(request)
    except (Merchant.DoesNotExist, User.DoesNotExist):
        return Response(
            {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = PayoutRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount_paise = serializer.validated_data["amount_paise"]
    bank_account_id = serializer.validated_data["bank_account_id"]

    with transaction.atomic():
        merchant = Merchant.objects.select_for_update().get(id=merchant.id)

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
        IdempotencyKey.objects.filter(
            key=idempotency_key, merchant=merchant, expires_at__lte=timezone.now()
        ).delete()

        held = Merchant.objects.filter(
            id=merchant.id,
            balance_paise__gte=F("held_balance_paise") + amount_paise,
        ).update(held_balance_paise=F("held_balance_paise") + amount_paise)
        if held != 1:
            return Response(
                {"error": "Insufficient available balance"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout = Payout.objects.create(
            merchant=merchant,
            amount_paise=amount_paise,
            bank_account_id=bank_account_id,
            idempotency_key=idempotency_key,
            status="pending",
        )

        response_data = PayoutSerializer(payout).data
        IdempotencyKey.objects.create(
            key=idempotency_key,
            merchant=merchant,
            response_data=response_data,
            response_status=status.HTTP_201_CREATED,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([])
def payout_history(request):
    try:
        merchant = get_request_merchant(request)
    except (Merchant.DoesNotExist, User.DoesNotExist):
        return Response(
            {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
        )

    payouts = Payout.objects.filter(merchant=merchant).order_by("-created_at")
    serializer = PayoutSerializer(payouts, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([])
def merchant_dashboard(request):
    try:
        merchant = Merchant.objects.annotate(
            available_balance=F("balance_paise") - F("held_balance_paise")
        ).get(id=get_request_merchant(request).id)
    except (Merchant.DoesNotExist, User.DoesNotExist):
        return Response(
            {"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND
        )

    recent_credits = merchant.credits.order_by("-created_at")[:10]
    recent_debits = merchant.payouts.order_by("-created_at")[:10]
    credit_total = merchant.credits.aggregate(total=Coalesce(Sum("amount_paise"), 0))[
        "total"
    ]
    completed_payout_total = merchant.payouts.filter(status="completed").aggregate(
        total=Coalesce(Sum("amount_paise"), 0)
    )["total"]

    return Response(
        {
            "available_balance_paise": merchant.available_balance,
            "held_balance_paise": merchant.held_balance_paise,
            "total_balance_paise": merchant.balance_paise,
            "ledger_credit_total_paise": credit_total,
            "ledger_completed_payout_total_paise": completed_payout_total,
            "recent_credits": CreditSerializer(recent_credits, many=True).data,
            "recent_debits": PayoutSerializer(recent_debits, many=True).data,
        }
    )

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Sum
from django.db.models.functions import Coalesce
from payouts.models import Merchant, Credit


class Command(BaseCommand):
    help = "Seed database with test data"

    def handle(self, *args, **options):
        # Create users and merchants
        merchants_data = [
            {
                "username": "merchant1",
                "email": "merchant1@example.com",
                "credits": [250000, 175000, 85000],
            },
            {
                "username": "merchant2",
                "email": "merchant2@example.com",
                "credits": [125000, 90000, 60000],
            },
            {
                "username": "merchant3",
                "email": "merchant3@example.com",
                "credits": [50000, 45000, 30000],
            },
        ]

        for data in merchants_data:
            user, created = User.objects.get_or_create(
                username=data["username"], defaults={"email": data["email"]}
            )
            if created:
                user.set_password("password123")
                user.save()
                self.stdout.write(f"Created user: {user.username}")
            else:
                self.stdout.write(f"User already exists: {user.username}")

            merchant, created = Merchant.objects.get_or_create(
                user=user, defaults={"balance_paise": 0, "held_balance_paise": 0}
            )
            if created:
                self.stdout.write(
                    f"Created merchant: {merchant.user.username}"
                )
            else:
                self.stdout.write(f"Merchant already exists: {merchant.user.username}")

            if not merchant.credits.exists():
                for index, amount in enumerate(data["credits"], start=1):
                    Credit.objects.create(
                        merchant=merchant,
                        amount_paise=amount,
                        description=f"Seed customer payment #{index}",
                    )
                self.stdout.write(f"Added credits to {merchant.user.username}")

            credit_total = merchant.credits.aggregate(
                total=Coalesce(Sum("amount_paise"), 0)
            )["total"]
            merchant.balance_paise = credit_total
            merchant.held_balance_paise = 0
            merchant.save(update_fields=["balance_paise", "held_balance_paise", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS("Successfully seeded database with test data")
        )

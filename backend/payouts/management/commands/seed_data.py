from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from payouts.models import Merchant, Credit
import random


class Command(BaseCommand):
    help = "Seed database with test data"

    def handle(self, *args, **options):
        # Create users and merchants
        merchants_data = [
            {
                "username": "merchant1",
                "email": "merchant1@example.com",
                "balance": 1000000,
            },  # 10,000 INR
            {
                "username": "merchant2",
                "email": "merchant2@example.com",
                "balance": 500000,
            },  # 5,000 INR
            {
                "username": "merchant3",
                "email": "merchant3@example.com",
                "balance": 200000,
            },  # 2,000 INR
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
                user=user, defaults={"balance_paise": data["balance"]}
            )
            if created:
                self.stdout.write(
                    f"Created merchant: {merchant.user.username} with balance {data['balance']} paise"
                )
            else:
                self.stdout.write(f"Merchant already exists: {merchant.user.username}")

            # Add some credits
            for i in range(5):
                amount = random.randint(10000, 100000)  # 100 to 1000 INR
                Credit.objects.create(
                    merchant=merchant,
                    amount_paise=amount,
                    description=f"Customer payment #{i+1}",
                )
                merchant.balance_paise += amount
                merchant.save()

            self.stdout.write(f"Added 5 credits to {merchant.user.username}")

        self.stdout.write(
            self.style.SUCCESS("Successfully seeded database with test data")
        )

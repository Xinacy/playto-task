from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payouts", "0002_integrity_constraints"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="merchant",
            constraint=models.CheckConstraint(
                condition=models.Q(balance_paise__gte=0),
                name="merchant_balance_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="merchant",
            constraint=models.CheckConstraint(
                condition=models.Q(held_balance_paise__gte=0),
                name="merchant_held_balance_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="merchant",
            constraint=models.CheckConstraint(
                condition=models.Q(balance_paise__gte=models.F("held_balance_paise")),
                name="merchant_balance_covers_holds",
            ),
        ),
        migrations.AddConstraint(
            model_name="credit",
            constraint=models.CheckConstraint(
                condition=models.Q(amount_paise__gt=0),
                name="credit_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="payout",
            constraint=models.CheckConstraint(
                condition=models.Q(amount_paise__gt=0),
                name="payout_amount_positive",
            ),
        ),
    ]

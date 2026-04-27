from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payouts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="idempotencykey",
            name="key",
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="idempotencykey",
            name="response_status",
            field=models.PositiveSmallIntegerField(default=201),
        ),
        migrations.AlterField(
            model_name="payout",
            name="idempotency_key",
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AddConstraint(
            model_name="idempotencykey",
            constraint=models.UniqueConstraint(
                fields=("merchant", "key"), name="unique_idempotency_key_per_merchant"
            ),
        ),
    ]

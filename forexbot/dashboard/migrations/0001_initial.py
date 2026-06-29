# Generated manually for Django 5.x

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Trade",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ticket", models.CharField(max_length=50, unique=True)),
                ("strategy", models.CharField(max_length=5)),
                ("symbol", models.CharField(max_length=20)),
                ("direction", models.CharField(max_length=5)),
                ("entry", models.FloatField()),
                ("sl", models.FloatField()),
                ("tp", models.FloatField()),
                ("lot", models.FloatField()),
                ("reason", models.TextField()),
                ("opened_at", models.DateTimeField()),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("pnl", models.FloatField(blank=True, null=True)),
                ("pips", models.FloatField(blank=True, null=True)),
                ("exit_reason", models.CharField(blank=True, max_length=200)),
            ],
            options={
                "ordering": ["-opened_at"],
            },
        ),
        migrations.CreateModel(
            name="DecisionLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ts", models.DateTimeField()),
                ("strategy", models.CharField(max_length=5)),
                ("symbol", models.CharField(max_length=20)),
                ("result", models.CharField(max_length=20)),
                ("reason", models.TextField(blank=True)),
                ("indicators", models.JSONField(default=dict)),
            ],
            options={
                "ordering": ["-ts"],
            },
        ),
    ]

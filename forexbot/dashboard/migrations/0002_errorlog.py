# Generated manually for Django 5.x

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ErrorLog",
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
                ("ts", models.DateTimeField(auto_now_add=True)),
                ("level", models.CharField(max_length=10)),
                ("context", models.CharField(max_length=200)),
                ("message", models.TextField()),
                ("traceback", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "Erro",
                "ordering": ["-ts"],
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemSetting",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=120, unique=True)),
                ("title", models.CharField(max_length=255)),
                (
                    "setting_type",
                    models.CharField(
                        choices=[
                            ("api_key", "API ключ"),
                            ("limit", "Лимит"),
                            ("feature_toggle", "Фича-тогл"),
                            ("periodic_task", "Периодическая задача"),
                            ("other", "Прочее"),
                        ],
                        default="other",
                        max_length=32,
                    ),
                ),
                ("value_text", models.TextField(blank=True, default="")),
                ("value_json", models.JSONField(blank=True, null=True)),
                ("value_number", models.IntegerField(blank=True, null=True)),
                ("is_enabled", models.BooleanField(default=True)),
                ("cron_expression", models.CharField(blank=True, default="", max_length=120)),
                ("description", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "admin_system_settings",
                "verbose_name": "Системная настройка",
                "verbose_name_plural": "Системные настройки",
            },
        ),
    ]

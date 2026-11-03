from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def backfill_priority_rule_contracts(apps, schema_editor):
    PriorityRuleSet = apps.get_model("projects", "PriorityRuleSet")
    # Import at migration time so the deployed contract is copied into each
    # historical ruleset, rather than pointing historical analyses at mutable
    # live configuration.
    from projects.scoring_contract import default_scoring_input_contract

    for rule_set in PriorityRuleSet.objects.all().iterator():
        rule_set.status = "active" if rule_set.is_active else "superseded"
        rule_set.input_contract = default_scoring_input_contract()
        if rule_set.is_active and not rule_set.activated_at:
            rule_set.activated_at = rule_set.created_at
        rule_set.save(update_fields=["status", "input_contract", "activated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0049_protected_system_agency"),
    ]

    operations = [
        migrations.AddField(
            model_name="priorityruleset",
            name="activated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="priorityruleset",
            name="activated_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activated_priority_rule_sets", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="priorityruleset",
            name="based_on",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="derived_rule_sets", to="projects.priorityruleset"),
        ),
        migrations.AddField(
            model_name="priorityruleset",
            name="change_note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="priorityruleset",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_priority_rule_sets", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="priorityruleset",
            name="input_contract",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="priorityruleset",
            name="status",
            field=models.CharField(choices=[("draft", "Draft"), ("active", "Active"), ("superseded", "Superseded")], db_index=True, default="active", max_length=20),
        ),
        migrations.AddField(
            model_name="priorityruleset",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name="PublicContactMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_submission_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("email", models.EmailField(max_length=254)),
                ("subject", models.CharField(blank=True, default="", max_length=300)),
                ("message", models.TextField()),
                ("request_fingerprint", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("receiver_delivery_status", models.CharField(choices=[("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("acknowledgement_delivery_status", models.CharField(choices=[("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("receiver_delivery_attempts", models.PositiveSmallIntegerField(default=0)),
                ("acknowledgement_delivery_attempts", models.PositiveSmallIntegerField(default=0)),
                ("receiver_sent_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledgement_sent_at", models.DateTimeField(blank=True, null=True)),
                ("receiver_last_error", models.CharField(blank=True, default="", max_length=300)),
                ("acknowledgement_last_error", models.CharField(blank=True, default="", max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="publiccontactmessage",
            index=models.Index(fields=["receiver_delivery_status", "-created_at"], name="contact_receiver_created_idx"),
        ),
        migrations.AddIndex(
            model_name="publiccontactmessage",
            index=models.Index(fields=["acknowledgement_delivery_status", "-created_at"], name="contact_ack_created_idx"),
        ),
        migrations.RunPython(backfill_priority_rule_contracts, migrations.RunPython.noop),
    ]

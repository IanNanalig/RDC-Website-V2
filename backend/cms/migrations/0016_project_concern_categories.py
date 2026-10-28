from django.db import migrations


DEFAULT_CATEGORIES = [
    {"code": "delay_discrepancy", "label": "Suspected project delay or discrepancy", "active": True},
    {"code": "reported_accomplishment", "label": "Concern involving reported project accomplishments", "active": True},
    {"code": "published_information", "label": "Inconsistency in project descriptions or published information", "active": True},
    {"code": "budget_funding", "label": "Concern involving reported budgets or funding", "active": True},
    {"code": "implementation_compliance", "label": "Potential implementation or compliance issue", "active": True},
    {"code": "other", "label": "Other project-related concern", "active": True},
]


def seed_project_concern_categories(apps, schema_editor):
    SiteSetting = apps.get_model("cms", "CMSSiteSetting")
    SiteSetting.objects.get_or_create(
        key="project-concern-categories",
        defaults={
            "value_json": {"categories": DEFAULT_CATEGORIES},
            "description": "Public categories used by the project concern reporting form.",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0015_add_collaborating_agencies_field"),
    ]

    operations = [
        migrations.RunPython(seed_project_concern_categories, migrations.RunPython.noop),
    ]

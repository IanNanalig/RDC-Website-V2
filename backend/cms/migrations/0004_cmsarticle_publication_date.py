from django.db import migrations, models


def backfill_article_publication_dates(apps, schema_editor):
    CMSArticle = apps.get_model("cms", "CMSArticle")
    for article in CMSArticle.objects.filter(publication_date__isnull=True).iterator():
        source = article.published_at or article.created_at
        if source:
            article.publication_date = source.date()
            article.save(update_fields=["publication_date"])


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0003_seed_complete_public_page_registry"),
    ]

    operations = [
        migrations.AddField(
            model_name="cmsarticle",
            name="publication_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_article_publication_dates, migrations.RunPython.noop),
    ]

from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def seed_public_content(apps, schema_editor):
    PublicContent = apps.get_model("projects", "PublicContent")

    entries = [
        {
            "slug": "home",
            "language": "en",
            "title": "Home",
            "summary": "Overview of the RDC-NCR portal with quick access to News, Publications, Projects, and the RDC portal login.",
            "body": "The Home page highlights RDC-NCR programs, quick access links, and navigation to public resources and the RDC Portal.",
            "tags": ["home", "overview", "quick access", "rdc portal"],
            "url": "/",
        },
        {
            "slug": "home",
            "language": "tl",
            "title": "Home",
            "summary": "Panimulang impormasyon ng RDC-NCR portal at mga mabilis na link para sa News, Publications, Projects, at portal login.",
            "body": "Makikita sa Home page ang mga pangunahing programa ng RDC-NCR at mga mabilis na link sa public resources at RDC Portal.",
            "tags": ["home", "panimula", "quick access", "rdc portal"],
            "url": "/",
        },
        {
            "slug": "about-rdc",
            "language": "en",
            "title": "About RDC",
            "summary": "Background on the RDC-NCR, its mandate, organizational structure, and committees.",
            "body": "The About RDC page explains the council's role, governance structure, and committee framework.",
            "tags": ["about", "rdc", "organizational structure", "committees"],
            "url": "/about",
        },
        {
            "slug": "about-rdc",
            "language": "tl",
            "title": "About RDC",
            "summary": "Impormasyon tungkol sa RDC-NCR, mandato nito, istruktura, at mga komite.",
            "body": "Ipinapaliwanag sa About RDC page ang papel ng konseho, istruktura ng pamamahala, at mga komite.",
            "tags": ["tungkol", "rdc", "istruktura", "komite"],
            "url": "/about",
        },
        {
            "slug": "news",
            "language": "en",
            "title": "News",
            "summary": "Latest RDC-NCR announcements and updates. Browse recent posts and public advisories here.",
            "body": "Use the News page to read RDC-NCR updates, announcements, and related articles.",
            "tags": ["news", "updates", "announcements"],
            "url": "/news",
        },
        {
            "slug": "news",
            "language": "tl",
            "title": "News",
            "summary": "Mga pinakabagong anunsyo at updates ng RDC-NCR. Dito makikita ang mga post at advisories.",
            "body": "Sa News page mababasa ang mga balita, anunsyo, at updates ng RDC-NCR.",
            "tags": ["balita", "updates", "anunsyo"],
            "url": "/news",
        },
        {
            "slug": "publications",
            "language": "en",
            "title": "Publications",
            "summary": "Access RDC-NCR documents and publications, including RDIP and related materials.",
            "body": "The Publications page provides downloadable RDC-NCR documents organized by category.",
            "tags": ["publications", "documents", "rdip", "downloads"],
            "url": "/publications",
        },
        {
            "slug": "publications",
            "language": "tl",
            "title": "Publications",
            "summary": "Mga dokumento at publikasyon ng RDC-NCR, kabilang ang RDIP at iba pang materyales.",
            "body": "Sa Publications page makukuha ang mga downloadable na dokumento ng RDC-NCR ayon sa kategorya.",
            "tags": ["publikasyon", "dokumento", "rdip", "download"],
            "url": "/publications",
        },
        {
            "slug": "projects-dashboard",
            "language": "en",
            "title": "Projects Dashboard",
            "summary": "Public projects dashboard with charts, filters, and project summaries for NCR.",
            "body": "The Projects page shows public project data, visualizations, and details for RDC-NCR.",
            "tags": ["projects", "dashboard", "charts", "public data"],
            "url": "/projects",
        },
        {
            "slug": "projects-dashboard",
            "language": "tl",
            "title": "Projects Dashboard",
            "summary": "Public dashboard ng mga proyekto na may charts, filters, at buod ng proyekto sa NCR.",
            "body": "Makikita sa Projects page ang public project data, visualization, at detalye ng mga proyekto ng RDC-NCR.",
            "tags": ["proyekto", "dashboard", "charts", "public data"],
            "url": "/projects",
        },
        {
            "slug": "regional-profile",
            "language": "en",
            "title": "Regional Profile",
            "summary": "Regional profile and key indicators for the National Capital Region.",
            "body": "The Regional Profile page provides NCR statistics, highlights, and regional context.",
            "tags": ["regional profile", "statistics", "ncr"],
            "url": "/regional-profile",
        },
        {
            "slug": "regional-profile",
            "language": "tl",
            "title": "Regional Profile",
            "summary": "Regional profile at mahahalagang datos para sa National Capital Region.",
            "body": "Sa Regional Profile page makikita ang mga statistics, highlights, at konteksto ng NCR.",
            "tags": ["regional profile", "datos", "ncr"],
            "url": "/regional-profile",
        },
        {
            "slug": "contact",
            "language": "en",
            "title": "Contact",
            "summary": "Send inquiries through the public contact form on the RDC-NCR website.",
            "body": "The Contact page lets visitors send messages and inquiries to RDC-NCR.",
            "tags": ["contact", "inquiry", "message"],
            "url": "/contact",
        },
        {
            "slug": "contact",
            "language": "tl",
            "title": "Contact",
            "summary": "Magpadala ng mensahe o inquiry gamit ang contact form ng RDC-NCR website.",
            "body": "Sa Contact page maaaring magpadala ng mensahe at katanungan sa RDC-NCR.",
            "tags": ["contact", "mensahe", "inquiry"],
            "url": "/contact",
        },
    ]

    for data in entries:
        PublicContent.objects.update_or_create(
            slug=data["slug"],
            language=data["language"],
            defaults=data,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0009_alter_useractivity_event"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicContent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.CharField(max_length=150)),
                ("title", models.CharField(max_length=200)),
                ("body", models.TextField(blank=True)),
                ("summary", models.TextField(blank=True)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("url", models.CharField(blank=True, max_length=200)),
                ("language", models.CharField(choices=[("en", "English"), ("tl", "Tagalog")], default="en", max_length=10)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["slug", "language"],
                "unique_together": {("slug", "language")},
            },
        ),
        migrations.CreateModel(
            name="PublicChatFAQ",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_normalized", models.CharField(max_length=255, unique=True)),
                ("question_sample", models.CharField(blank=True, max_length=255)),
                ("count", models.IntegerField(default=1)),
                ("last_asked", models.DateTimeField(default=timezone.now)),
                (
                    "last_matched_content",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="faq_matches",
                        to="projects.publiccontent",
                    ),
                ),
            ],
            options={
                "ordering": ["-count", "-last_asked"],
            },
        ),
        migrations.RunPython(seed_public_content, migrations.RunPython.noop),
    ]


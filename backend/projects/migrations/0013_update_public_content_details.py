from django.db import migrations


def update_public_content_details(apps, schema_editor):
    PublicContent = apps.get_model("projects", "PublicContent")

    updates = [
        {
            "slug": "home",
            "language": "en",
            "summary": "Quick access to RDC-NCR News, Publications (RDIP docs), Projects Dashboard, Contact, and portal login.",
            "body": (
                "Use the Home page to jump to News updates, Publications, the public Projects Dashboard, "
                "Regional Profile, and the Contact form."
            ),
            "tags": ["home", "quick access", "news", "publications", "projects", "contact"],
        },
        {
            "slug": "home",
            "language": "tl",
            "summary": "Mabilis na access sa News, Publications (RDIP docs), Projects Dashboard, Contact, at portal login ng RDC-NCR.",
            "body": (
                "Sa Home page, mabilis kang makakapunta sa News, Publications, public Projects Dashboard, "
                "Regional Profile, at Contact form."
            ),
            "tags": ["home", "balita", "publikasyon", "proyekto", "contact"],
        },
        {
            "slug": "about-rdc",
            "language": "en",
            "summary": "RDC-NCR mandate, organizational structure, committees, and resolutions archive.",
            "body": (
                "The About RDC page explains the council’s mandate, organizational structure, voting/non‑voting members, "
                "sectoral and affiliate committees, and the resolutions archive. Voting members include 17 MM Mayors."
            ),
            "tags": ["about", "mandate", "structure", "committees", "resolutions", "lgus"],
        },
        {
            "slug": "about-rdc",
            "language": "tl",
            "summary": "Mandato, istruktura, mga komite, at resolutions archive ng RDC-NCR.",
            "body": (
                "Ipinaliliwanag sa About RDC page ang mandato, istruktura, voting at non‑voting members, mga komite, "
                "at resolutions archive ng RDC‑NCR. Kasama sa voting members ang 17 MM Mayors."
            ),
            "tags": ["tungkol", "mandato", "istruktura", "komite", "resolusyon", "lgus"],
        },
        {
            "slug": "news",
            "language": "en",
            "summary": "Latest announcements, advisories, and RDC-NCR updates. Check here for schedules and events.",
            "body": "The News page lists RDC-NCR announcements, public advisories, and event updates.",
            "tags": ["news", "announcements", "advisories", "events", "schedule"],
        },
        {
            "slug": "news",
            "language": "tl",
            "summary": "Mga anunsyo, advisories, at updates ng RDC-NCR. Dito rin makikita ang schedules at events.",
            "body": "Sa News page makikita ang mga anunsyo, advisories, at updates ng RDC-NCR.",
            "tags": ["balita", "anunsyo", "events", "schedule"],
        },
        {
            "slug": "publications",
            "language": "en",
            "summary": "Download RDC-NCR documents (RDIP, manuals, annexes, brochures) from Publications.",
            "body": (
                "Publications are grouped by category. Open a document card and click View or Download to access the file."
            ),
            "tags": ["publications", "documents", "rdip", "download", "pdf"],
        },
        {
            "slug": "publications",
            "language": "tl",
            "summary": "Mag-download ng RDC-NCR documents (RDIP, manuals, annexes, brochures) sa Publications.",
            "body": "Naka‑kategorya ang Publications. Buksan ang document card at i‑click ang View o Download.",
            "tags": ["publikasyon", "dokumento", "rdip", "download", "pdf"],
        },
        {
            "slug": "projects-dashboard",
            "language": "en",
            "summary": "Public Projects Dashboard with charts, filters, and project summaries for NCR.",
            "body": (
                "Use the Projects Dashboard to explore project data by agency or status, view charts, and open project details."
            ),
            "tags": ["projects", "dashboard", "charts", "filters", "public data"],
        },
        {
            "slug": "projects-dashboard",
            "language": "tl",
            "summary": "Public Projects Dashboard na may charts, filters, at buod ng proyekto sa NCR.",
            "body": (
                "Sa Projects Dashboard, maaaring mag‑filter ayon sa ahensya o status, tingnan ang charts, at buksan ang detalye."
            ),
            "tags": ["proyekto", "dashboard", "charts", "filters", "public data"],
        },
        {
            "slug": "regional-profile",
            "language": "en",
            "summary": "Regional Profile with NCR statistics, key indicators, and highlights.",
            "body": "The Regional Profile page shows NCR indicators and regional context data.",
            "tags": ["regional profile", "statistics", "indicators", "ncr"],
        },
        {
            "slug": "regional-profile",
            "language": "tl",
            "summary": "Regional Profile na may NCR statistics, indicators, at highlights.",
            "body": "Sa Regional Profile page makikita ang NCR indicators at mga pangunahing datos.",
            "tags": ["regional profile", "datos", "indikador", "ncr"],
        },
    ]

    for update in updates:
        PublicContent.objects.update_or_create(
            slug=update["slug"],
            language=update["language"],
            defaults=update,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0012_update_public_content_contact"),
    ]

    operations = [
        migrations.RunPython(update_public_content_details, migrations.RunPython.noop),
    ]


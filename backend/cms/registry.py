"""Application-owned public page and section structure.

The CMS may edit content for these records, but it must never create, remove,
rename, hide, or reorder the structural records themselves.
"""

PUBLIC_CMS_PAGE_REGISTRY = {
    "home": {
        "title": "Home",
        "sections": (
            ("hero-carousel", "hero_carousel"),
            ("development-plans", "document_group"),
            ("investment-programming", "document_group"),
            ("monitoring-evaluation", "document_group"),
            ("dashboard-teaser", "dashboard_teaser"),
            ("latest-media", "news_preview"),
            ("upcoming-events", "events_preview"),
        ),
    },
    "regional-profile": {
        "title": "Region Profile",
        "sections": (
            ("region-hero", "text"),
            ("regional-overview", "cards"),
            ("geographic-coverage", "location_map"),
            ("lgu-directory", "document_group"),
        ),
    },
    "publications": {
        "title": "Publications",
        "sections": (("publication-catalog", "publication_catalog"),),
    },
    "news": {
        "title": "News",
        "sections": (("news-hero", "text"), ("news-listing", "news_listing")),
    },
    "about-rdc": {
        "title": "About RDC",
        "sections": (
            ("about-hero", "text"),
            ("legal-basis", "document_group"),
            ("committees", "document_group"),
            ("organization-structure", "text"),
            ("resolutions-archive", "text"),
        ),
    },
    "contact": {
        "title": "Contact Us",
        "sections": (
            ("contact-hero", "text"),
            ("main-office", "contact_info"),
            ("location-map", "location_map"),
            ("message-form", "form_intro"),
        ),
    },
    "projects-dashboard": {
        "title": "Projects Dashboard",
        "sections": (
            ("projects-hero", "text"),
            ("projects-updates", "text"),
            ("projects-data-note", "text"),
        ),
    },
}

# News landing-page copy and Projects Dashboard copy remain publicly served for
# backward compatibility, but their content is no longer editable as a CMS page.
EDITABLE_CMS_PAGE_SLUGS = (
    "home",
    "regional-profile",
    "publications",
    "about-rdc",
    "contact",
)
EDITABLE_CMS_PAGE_REGISTRY = {
    slug: PUBLIC_CMS_PAGE_REGISTRY[slug]
    for slug in EDITABLE_CMS_PAGE_SLUGS
}

# Kept as a compatibility alias for seed/audit/public rendering code that needs
# the complete application-owned public structure.
FIXED_CMS_PAGE_REGISTRY = PUBLIC_CMS_PAGE_REGISTRY


def fixed_page_definition(slug):
    return PUBLIC_CMS_PAGE_REGISTRY.get(str(slug or "").strip())


def editable_page_definition(slug):
    return EDITABLE_CMS_PAGE_REGISTRY.get(str(slug or "").strip())


def fixed_section_definition(page_slug, section_key):
    page = fixed_page_definition(page_slug)
    if not page:
        return None
    for order, (key, section_type) in enumerate(page["sections"], start=1):
        if key == section_key:
            return {"key": key, "type": section_type, "order": order}
    return None


def editable_section_definition(page_slug, section_key):
    page = editable_page_definition(page_slug)
    if not page:
        return None
    for order, (key, section_type) in enumerate(page["sections"], start=1):
        if key == section_key:
            return {"key": key, "type": section_type, "order": order}
    return None


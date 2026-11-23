from django.db.models import Q

from .models import Project


def public_project_queryset():
    """Return the same public-eligible projects for every public workflow."""
    endorsed_archives = Project.objects.filter(archived=True, validated=True).exclude(
        workflow_status__in=(Project.WORKFLOW_DRAFT, "rejected"),
    ).filter(
        Q(workflow_status=Project.WORKFLOW_VALIDATED)
        | Q(revisions__state="endorsed", revisions__is_public_current=True)
    )
    return Project.objects.filter(validated=True).filter(
        Q(archived=False, is_active=True) | Q(pk__in=endorsed_archives.values("pk"))
    )

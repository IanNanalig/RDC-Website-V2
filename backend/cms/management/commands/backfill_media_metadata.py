from pathlib import Path

from django.core.management.base import BaseCommand

from cms.models import CMSMediaAsset
from cms.services.media_validation import CMSMediaValidationError, extract_media_metadata


class Command(BaseCommand):
    help = "Backfill metadata for a bounded number of existing CMS files."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 500))
        files = CMSMediaAsset.objects.filter(original_filename="").order_by("id")[:limit]
        for asset in files:
            try:
                with asset.file.open("rb") as stream:
                    metadata = extract_media_metadata(stream, asset.file_type)
                asset.original_filename = Path(asset.file.name).name[:255]
                for field in ("width", "height", "duration_seconds"):
                    setattr(asset, field, metadata.get(field))
                if not options["dry_run"]:
                    asset.save(update_fields=["original_filename", "width", "height", "duration_seconds"])
                self.stdout.write(f"{asset.pk}: metadata {'checked' if options['dry_run'] else 'saved'}")
            except (OSError, CMSMediaValidationError) as exc:
                self.stderr.write(f"{asset.pk}: {exc}")

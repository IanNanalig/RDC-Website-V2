from django.core.management.base import BaseCommand

from ai_engine.historical_index import index_status, rebuild_historical_batch, retry_historical_references


class Command(BaseCommand):
    help = "Preview or rebuild the searchable index of validator-endorsed projects."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true", help="Rebuild eligible references.")
        mode.add_argument("--retry", action="store_true", help="Retry up to 25 due indexing jobs.")

    def handle(self, **options):
        if options["retry"]:
            retry_historical_references(limit=25)
            self.stdout.write(str(index_status()))
            return
        cursor = scanned = scheduled = 0
        while cursor is not None:
            batch = rebuild_historical_batch(after=cursor, dry_run=not options["apply"])
            cursor = batch["next"]
            scanned += batch["scanned"]
            scheduled += batch["scheduled"]
        mode = "rebuild" if options["apply"] else "dry run"
        self.stdout.write(f"{mode}: {scheduled} eligible of {scanned} validated projects")
        self.stdout.write(str(index_status()))

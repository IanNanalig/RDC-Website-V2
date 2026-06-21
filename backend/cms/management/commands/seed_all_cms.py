from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed and publish every built-in CMS page snapshot used by the public website."

    seed_commands = [
        "seed_home_cms",
        "seed_about_cms",
        "seed_contact_cms",
        "seed_region_profile_cms",
        "seed_publications_cms",
    ]

    def handle(self, *args, **options):
        self.stdout.write("Seeding all public CMS pages...")
        for command_name in self.seed_commands:
            self.stdout.write(f"- Running {command_name}")
            call_command(command_name)
        self.stdout.write(self.style.SUCCESS("All built-in CMS page snapshots were seeded and published."))

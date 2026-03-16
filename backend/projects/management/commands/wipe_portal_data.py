from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from projects.models import AccessRequest, Project, User, UserActivity


class Command(BaseCommand):
    help = "Wipe portal data (users/projects/requests/activity) while keeping a specific admin user."

    def add_arguments(self, parser):
        parser.add_argument("--keep-email", dest="keep_email", help="Email of the admin to keep.")
        parser.add_argument("--keep-username", dest="keep_username", help="Username of the admin to keep.")
        parser.add_argument("--dry-run", action="store_true", help="Show counts without deleting.")

    def handle(self, *args, **options):
        keep_email = (options.get("keep_email") or "").strip().lower()
        keep_username = (options.get("keep_username") or "").strip()
        dry_run = options.get("dry_run", False)

        if not keep_email and not keep_username:
            raise CommandError("Provide --keep-email or --keep-username to preserve an admin account.")

        admin_qs = User.objects.filter(role="admin")
        if keep_email:
            admin_qs = admin_qs.filter(email__iexact=keep_email)
        if keep_username:
            admin_qs = admin_qs.filter(username=keep_username)

        admin_user = admin_qs.first()
        if not admin_user:
            raise CommandError("Admin account to keep was not found.")

        users_to_delete = User.objects.exclude(id=admin_user.id)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run only. No data deleted."))
            self.stdout.write(f"Users to delete: {users_to_delete.count()}")
            self.stdout.write(f"Projects to delete: {Project.objects.count()}")
            self.stdout.write(f"Access requests to delete: {AccessRequest.objects.count()}")
            self.stdout.write(f"Activity logs to delete: {UserActivity.objects.count()}")
            return

        with transaction.atomic():
            UserActivity.objects.all().delete()
            AccessRequest.objects.all().delete()
            Project.objects.all().delete()
            users_to_delete.delete()

        self.stdout.write(self.style.SUCCESS("Portal data wiped. Admin account preserved."))

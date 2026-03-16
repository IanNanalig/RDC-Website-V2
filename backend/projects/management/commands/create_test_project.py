from django.core.management.base import BaseCommand
from projects.models import User, Project
from django.utils import timezone

class Command(BaseCommand):
    help = 'Create a test employee user and a test project to verify dashboards'

    def handle(self, *args, **options):
        user = User.objects.filter(role='employee').first()
        if not user:
            user = User.objects.create_user(username='auto_employee', password='testpass', email='auto@example.com')
            user.role = 'employee'
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created user {user.username}'))
        else:
            self.stdout.write(self.style.NOTICE(f'Found existing employee user: {user.username}'))

        project = Project.objects.create(
            title='Auto Test Project',
            description='Project created by automated test command',
            agency='Auto Agency',
            budget=50000,
            completion=0,
            submitted_by=user,
            status='draft'
        )
        self.stdout.write(self.style.SUCCESS(f'Created project id={project.id} title="{project.title}"'))

        total = Project.objects.count()
        pending = Project.objects.filter(status='pending_validation').count()
        my_projects = Project.objects.filter(submitted_by=user).count()

        self.stdout.write(self.style.SUCCESS(f'Total projects: {total}'))
        self.stdout.write(self.style.SUCCESS(f'Pending projects: {pending}'))
        self.stdout.write(self.style.SUCCESS(f'My projects for {user.username}: {my_projects}'))

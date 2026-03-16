from django.core.management.base import BaseCommand
from projects.models import Project, User

class Command(BaseCommand):
    help = 'Load demo users and projects for RDC-NCR dashboard'

    def handle(self, *args, **options):
        # Create demo users
        admin, _ = User.objects.get_or_create(
            username='admin',
            defaults={'role': 'admin', 'email': 'admin@example.com'}
        )
        admin.set_password('adminpass')
        admin.save()

        validator, _ = User.objects.get_or_create(
            username='validator',
            defaults={'role': 'validator', 'email': 'validator@example.com'}
        )
        validator.set_password('validatorpass')
        validator.save()

        staff, _ = User.objects.get_or_create(
            username='staff',
            defaults={'role': 'staff', 'email': 'staff@example.com'}
        )
        staff.set_password('staffpass')
        staff.save()

        # Create demo projects
        projects = [
            {
                'name': 'Manila Bay Clean-Up',
                'implementing_agency': 'DENR',
                'municipality': 'Manila',
                'status': 'ongoing',
                'cost': 500000000,
                'latitude': 14.5995,
                'longitude': 120.9842,
                'year': 2025
            },
            {
                'name': 'Quezon City Green Park',
                'implementing_agency': 'DPWH',
                'municipality': 'Quezon City',
                'status': 'completed',
                'cost': 200000000,
                'latitude': 14.6760,
                'longitude': 121.0437,
                'year': 2024
            },
            {
                'name': 'Pasig River Rehabilitation',
                'implementing_agency': 'MMDA',
                'municipality': 'Pasig',
                'status': 'planning',
                'cost': 150000000,
                'latitude': 14.5764,
                'longitude': 121.0851,
                'year': 2026
            },
        ]

        for p in projects:
            Project.objects.create(created_by=staff, **p)

        self.stdout.write(self.style.SUCCESS('✅ Demo users and projects loaded successfully'))

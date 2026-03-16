from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_enable_extensions'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='agency',
            field=models.CharField(max_length=200, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='budget',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='project',
            name='completion',
            field=models.IntegerField(default=0),
        ),
    ]

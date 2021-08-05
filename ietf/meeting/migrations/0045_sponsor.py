# Generated by Django 2.2.24 on 2021-08-05 10:24

from django.db import migrations, models
import django.db.models.deletion
import ietf.meeting.models
import ietf.utils.models
import ietf.utils.storage
import ietf.utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0044_proceedingsmaterial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sponsor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('logo', models.ImageField(height_field='logo_height', storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=ietf.meeting.models._sponsor_upload_path, validators=[ietf.utils.validators.MaxImageSizeValidator(600, 600), ietf.utils.validators.validate_file_size, ietf.utils.validators.WrappedValidator(ietf.utils.validators.validate_file_extension, ['.png', '.jpg']), ietf.utils.validators.WrappedValidator(ietf.utils.validators.validate_mime_type, ['image/jpeg', 'image/png'])], width_field='logo_width')),
                ('logo_width', models.PositiveIntegerField()),
                ('logo_height', models.PositiveIntegerField()),
                ('meeting', ietf.utils.models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sponsors', to='meeting.Meeting')),
            ],
            options={
                'unique_together': {('meeting', 'name')},
            },
        ),
    ]

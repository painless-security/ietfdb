# Generated by Django 2.2.24 on 2021-09-16 18:04

from django.db import migrations
import django.db.models.deletion
import ietf.utils.models


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0035_populate_sessionpurposename'),
        ('meeting', '0047_auto_20210906_0702'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='purpose',
            field=ietf.utils.models.ForeignKey(default='none', help_text='Purpose of the session', on_delete=django.db.models.deletion.CASCADE, to='name.SessionPurposeName'),
            preserve_default=False,
        ),
    ]

# Copyright The IETF Trust 2021 All Rights Reserved

# Generated by Django 2.2.24 on 2021-07-26 16:55

from django.db import migrations


def forward(apps, schema_editor):
    ProceedingsMaterialTypeName = apps.get_model('name', 'ProceedingsMaterialTypeName')
    names = [
        {'slug': 'supporters', 'name': 'Sponsors and Supporters', 'desc': 'Sponsors and supporters', 'order': 0},
        {'slug': 'host_speaker_series', 'name': 'Host Speaker Series', 'desc': 'Host speaker series', 'order': 1},
        {'slug': 'social_event', 'name': 'Social Event', 'desc': 'Social event', 'order': 2},
        {'slug': 'wiki', 'name': 'Meeting Wiki', 'desc': 'Meeting wiki', 'order': 3},
        {'slug': 'additional_information', 'name': 'Additional Information', 'desc': 'Any other materials', 'order': 4},
    ]
    for name in names:
        ProceedingsMaterialTypeName.objects.create(used=True, **name)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0028_proceedingsmaterialtypename'),
        ('meeting', '0046_meetinghost'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]

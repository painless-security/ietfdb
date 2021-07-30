# Copyright The IETF Trust 2021 All Rights Reserved
# Generated by Django 2.2.19 on 2021-04-02 12:03

from django.db import migrations, models


def forward(apps, schema_editor):
    GroupFeatures = apps.get_model('group', 'GroupFeatures')

    # map AgendaFilterTypeName slug to group types - unlisted get 'none'
    filter_types = dict(
        # list previously hard coded in agenda view, plus 'review'
        normal={'wg', 'ag', 'rg', 'rag', 'iab', 'program', 'review'},
        heading={'area', 'ietf', 'irtf'},
        special={'team', 'adhoc'},
    )

    for ft, group_types in filter_types.items():
        for gf in GroupFeatures.objects.filter(type__slug__in=group_types):
            gf.agenda_filter_type_id = ft
            gf.save()


def reverse(apps, schema_editor):
    pass  # nothing to do, model will be deleted anyway


class Migration(migrations.Migration):
    dependencies = [
        ('group', '0045_groupfeatures_agenda_filter_type'),
        ('meeting', '0042_meeting_group_conflict_types'),  # fix interleaving
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]

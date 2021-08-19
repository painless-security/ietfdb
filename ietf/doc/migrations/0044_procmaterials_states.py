# Copyright The IETF Trust 2021 All Rights Reserved

# Generated by Django 2.2.23 on 2021-05-21 13:29

from django.db import migrations

def forward(apps, schema_editor):
    StateType = apps.get_model('doc', 'StateType')
    State = apps.get_model('doc', 'State')

    StateType.objects.create(slug='procmaterials', label='Proceedings Materials State')
    active = State.objects.create(type_id='procmaterials', slug='active', name='Active', used=True, desc='The material is active', order=0)
    removed = State.objects.create(type_id='procmaterials', slug='removed', name='Removed', used=True, desc='The material is removed', order=1)

    active.next_states.set([removed])
    removed.next_states.set([active])

def reverse(apps, schema_editor):
    StateType = apps.get_model('doc', 'StateType')
    State = apps.get_model('doc', 'State')
    State.objects.filter(type_id='procmaterials').delete()
    StateType.objects.filter(slug='procmaterials').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0043_bofreq_docevents'),
        ('name', '0032_add_procmaterials'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
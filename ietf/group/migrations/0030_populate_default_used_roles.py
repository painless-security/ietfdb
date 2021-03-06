# Generated by Django 2.0.13 on 2020-05-22 11:41

from django.db import migrations

grouptype_defaults = {
    'adhoc': ['matman', 'ad', 'chair', 'lead'],
    'admin': ['member', 'chair'],
    'ag': ['ad', 'chair', 'secr'],
    'area': ['ad'],
    'dir': ['ad', 'chair', 'reviewer', 'secr'],
    'review': ['ad', 'chair', 'reviewer', 'secr'],
    'iab': ['chair'],
    'iana': ['auth'],
    'iesg': [],
    'ietf': ['ad', 'member', 'comdir', 'delegate', 'execdir', 'recman', 'secr', 'trac-editor', 'trac-admin', 'chair'],
    'individ': ['ad'],
    'irtf': ['member', 'atlarge', 'chair'],
    'ise': ['chair'],
    'isoc': ['chair', 'ceo'],
    'nomcom': ['member', 'advisor', 'liaison', 'chair', 'techadv'],
    'program': ['member', 'chair', 'lead'],
    'rfcedtyp': ['auth', 'chair'],
    'rg': ['chair', 'techadv', 'secr', 'delegate'],
    'sdo': ['liaiman', 'ceo', 'coord', 'auth', 'chair'],
    'team': ['ad', 'member', 'delegate', 'secr', 'liaison', 'atlarge', 'chair', 'matman', 'techadv'],
    'wg': ['ad', 'editor', 'delegate', 'secr', 'chair', 'matman', 'techadv'],
}

def forward(apps, schema_editor):
    GroupFeatures = apps.get_model('group','GroupFeatures')
    for type_id, roles in grouptype_defaults.items():
        GroupFeatures.objects.filter(type_id=type_id).update(default_used_roles=roles)

def reverse(apps, schema_editor):
    pass # intentional

class Migration(migrations.Migration):

    dependencies = [
        ('group', '0029_add_used_roles_and_default_used_roles'),
        ('stats', '0003_meetingregistration_attended'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]

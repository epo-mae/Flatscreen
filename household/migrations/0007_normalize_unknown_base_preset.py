"""Repair any base_preset value that no longer has a preset behind it.

A preset that existed in code (and was written to the household during a
preview/review run) can be removed later, leaving a stale value that settings
would otherwise reject with a KeyError.
"""

from django.db import migrations

KNOWN_PRESETS = ('classic', 'minimal', 'soft', 'editorial', 'dense')


def normalize_unknown_preset(apps, schema_editor):
    Household = apps.get_model('household', 'Household')
    for household in Household.objects.exclude(base_preset__in=KNOWN_PRESETS):
        household.base_preset = 'classic'
        household.appearance_overrides = {}
        household.save(update_fields=['base_preset', 'appearance_overrides'])


class Migration(migrations.Migration):

    dependencies = [
        ('household', '0006_alter_household_base_preset'),
    ]

    operations = [
        migrations.RunPython(normalize_unknown_preset, migrations.RunPython.noop),
    ]
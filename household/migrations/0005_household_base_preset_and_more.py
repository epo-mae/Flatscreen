"""Move the flat appearance values onto the new base_preset + overrides model.

Backward compatible: a household using the stock Classic look stays Classic with
no overrides. Any customised values are preserved as sparse overrides, so the
interface keeps its customised appearance (shown as "Classic - customised").
"""

from django.db import migrations, models

from household.appearance import overrides_from_legacy


def forward(apps, schema_editor):
    Household = apps.get_model('household', 'Household')
    for household in Household.objects.all():
        base_preset = getattr(household, 'base_preset', 'classic') or 'classic'
        legacy = household.appearance_values or {}
        household.appearance_overrides = overrides_from_legacy(base_preset, legacy)
        household.save(update_fields=['appearance_overrides'])


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('household', '0004_household_appearance_preset_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='household',
            old_name='appearance_preset',
            new_name='base_preset',
        ),
        migrations.AddField(
            model_name='household',
            name='appearance_overrides',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(forward, backward),
        migrations.RemoveField(
            model_name='household',
            name='appearance_values',
        ),
    ]
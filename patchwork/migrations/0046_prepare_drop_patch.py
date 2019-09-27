# Generated by Django 2.2.5 on 2019-09-29 23:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('patchwork', '0045_drop_patch_project'),
    ]

    operations = [
        migrations.AlterField(
            model_name='check',
            name='patch',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='patchwork.Submission'),
        ),
        migrations.AlterField(
            model_name='bundle',
            name='patches',
            field=models.ManyToManyField(through='patchwork.BundlePatch', to='patchwork.Submission'),
        ),
        migrations.AlterField(
            model_name='bundlepatch',
            name='patch',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='patchwork.Submission'),
        ),
        migrations.AlterField(
            model_name='event',
            name='patch',
            field=models.ForeignKey(blank=True, help_text=b'The patch that this event was created for.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='patchwork.Submission'),
        ),
        migrations.AlterField(
            model_name='patchchangenotification',
            name='patch',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='patchwork.Submission'),
        ),
        migrations.AlterModelOptions(
            name='patch',
            options={'verbose_name_plural': 'Patches'},
        ),
    ]

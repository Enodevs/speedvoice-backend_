# Generated by Django 5.1.4 on 2025-01-12 15:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_alter_invoice_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='status',
            field=models.CharField(choices=[('paid', 'Paid'), ('pending', 'Pending'), ('unpaid', 'Unpaid'), ('draft', 'Draft')], default='pending', max_length=100),
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_merge_20260603_0810'),
    ]

    operations = [
        migrations.CreateModel(
            name='UsuarioHub',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hub', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.hub')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.usuario')),
            ],
        ),
    ]

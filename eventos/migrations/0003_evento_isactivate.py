from django.db import migrations, models


def adicionar_coluna_isactivate(apps, schema_editor):
    Evento = apps.get_model('eventos', 'Evento')
    tabela = Evento._meta.db_table
    coluna = 'isActivate'

    with schema_editor.connection.cursor() as cursor:
        colunas_existentes = {
            item.name
            for item in schema_editor.connection.introspection.get_table_description(
                cursor, tabela
            )
        }

    if coluna not in colunas_existentes:
        campo = Evento._meta.get_field(coluna)
        schema_editor.add_field(Evento, campo)


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0002_evento_empresa'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='evento',
                    name='isActivate',
                    field=models.BooleanField(default=True),
                ),
            ],
        ),
        migrations.RunPython(
            adicionar_coluna_isactivate,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
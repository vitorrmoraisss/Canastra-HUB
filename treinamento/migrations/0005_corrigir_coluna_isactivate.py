from django.db import migrations


def adicionar_coluna_isactivate(apps, schema_editor):
    Treinamento = apps.get_model('treinamento', 'Treinamento')
    tabela = Treinamento._meta.db_table
    coluna = 'isActivate'

    with schema_editor.connection.cursor() as cursor:
        colunas_existentes = {
            item.name
            for item in schema_editor.connection.introspection.get_table_description(
                cursor, tabela
            )
        }

    if coluna not in colunas_existentes:
        campo = Treinamento._meta.get_field(coluna)
        schema_editor.add_field(Treinamento, campo)


class Migration(migrations.Migration):

    dependencies = [
        ('treinamento', '0004_treinamento_isactivate'),
    ]

    operations = [
        migrations.RunPython(
            adicionar_coluna_isactivate,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

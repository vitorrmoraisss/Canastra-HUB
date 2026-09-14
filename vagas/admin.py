from django.contrib import admin
from vagas.models import Vagas, UsuarioVaga, CursoVaga


@admin.register(UsuarioVaga)
class UsuarioVagaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'vaga', 'status', 'data_candidatura',
                     'data_status', 'ifmg_no_momento_contratacao')
    list_filter = ('status', 'ifmg_no_momento_contratacao')
    search_fields = ('usuario__nome_social', 'vaga__cargo_vaga')


admin.site.register(Vagas)
admin.site.register(CursoVaga)

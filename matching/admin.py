from django.contrib import admin

from .models import EnvioVagasEmail, PreferenciaEmailVagas


@admin.register(EnvioVagasEmail)
class EnvioVagasEmailAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'email', 'semana', 'status', 'tentativas', 'enviado_em', 'atualizado_em')
    list_filter = ('status', 'semana')
    search_fields = ('email', 'usuario__user__nome')
    readonly_fields = ('usuario', 'email', 'semana', 'status', 'vagas', 'tentativas', 'erro',
                       'criado_em', 'atualizado_em', 'enviado_em')


@admin.register(PreferenciaEmailVagas)
class PreferenciaEmailVagasAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'receber_vagas', 'atualizado_em')
    list_filter = ('receber_vagas',)
    search_fields = ('usuario__user__email', 'usuario__user__nome')

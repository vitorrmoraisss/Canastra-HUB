from django.contrib import admin

from core.models import Hub, Sala, SalaImagem


class SalaImagemInline(admin.TabularInline):
    model = SalaImagem
    extra = 1


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    inlines = [SalaImagemInline]


admin.site.register(Hub)
from .models import InteresseCompra, MensagemContato

# Register your models here.
admin.site.register(InteresseCompra)


@admin.register(MensagemContato)
class MensagemContatoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'tipo', 'criado_em', 'respondida')
    list_filter = ('tipo',)
    readonly_fields = [f.name for f in MensagemContato._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

from django.contrib import admin

from core.models import Hub, Sala, SalaImagem


class SalaImagemInline(admin.TabularInline):
    model = SalaImagem
    extra = 1


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    inlines = [SalaImagemInline]


admin.site.register(Hub)
from .models import InteresseCompra

# Register your models here.
admin.site.register(InteresseCompra)

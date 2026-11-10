from urllib.parse import urlencode

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.urls import path, include, reverse


def admin_login(request):
    """O login do Django admin passa pelo login com verificação em duas etapas."""
    destino = request.GET.get('next') or '/admin/'
    return redirect(f"{reverse('core:login')}?{urlencode({'next': destino})}")


urlpatterns = [
    path("admin/login/", admin_login, name="admin_login"),
    path("admin/", admin.site.urls),
    path('', include('core.urls')),
    path('empresa/', include('empresa.urls')),
    path('vagas/', include('vagas.urls')),
    path('administrador/', include('administrador.urls')),
    path('treinamento/', include('treinamento.urls')),
    path('perfil/', include('perfil.urls')),
    path('eventos/', include('eventos.urls')),


    # Centralizado com namespace
    path('agendamento/', include('agendamento.urls', namespace='agendamento')),
    path('matching/', include('matching.urls')),
    

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)

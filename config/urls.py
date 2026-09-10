from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', include('core.urls')),  
    path('empresa/', include('empresa.urls')),  
    path('vagas/', include('vagas.urls')),
    path('administrador/', include('administrador.urls')),
    path('treinamento/', include('treinamento.urls')),
    path('perfil/', include('perfil.urls')),
    path('eventos/', include('eventos.urls')),
    path('matching/', include('matching.urls')),
    path('agendamento/', include('agendamento.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
from .models import ConfiguracaoSite


def configuracao_site(request):
    configuracao = ConfiguracaoSite.objects.filter(pk=1).first()

    return {
        'configuracao_site': configuracao
    }
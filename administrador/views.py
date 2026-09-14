from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from core.models import * 

# Create your views here.



@login_required
def areaAdm(request):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')
    
    return render(request, "areaAdm.html")

@login_required
def gerenciarHubs(request):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')
    
    hubs_lista = Hub.objects.order_by('-isActive')
    return render(request, "gerenciarHubs.html", {'hubs_lista': hubs_lista})

@login_required
def cadastrarHub(request):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')
    
    if request.method == 'POST':
        nome_hub = request.POST.get('txtNomeHub')
        foto_hub = request.FILES.get("fleFotoHub")  
        descricao_hub= request.POST.get("txtDescricaoHub") 
        
        if Hub.objects.filter(nome_hub=nome_hub):
            messages.error(request, "Hub já Cadastrado no sistema")
            return redirect('administrador:gerenciarHubs') 

        hubs = Hub.objects.create(    
        nome_hub=nome_hub,
        foto_hub = foto_hub,
        descricao_hub = descricao_hub
      )

        hubs.save()
        messages.success(request, ("Hub cadastrado com sucesso"))
        return redirect('administrador:cadastrarHub')

    return render(request, "cadastrar_hubs.html")

@login_required
def alterarHub(request):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')
    
    if request.method == 'POST':
        id = request.POST.get('idhub')
        nome_hub = request.POST.get('txtNomeHub')
        foto_hub = request.FILES.get("fleFotoHub")  
        descricao_hub= request.POST.get("txtDescricaoHub")

        hub = Hub.objects.get(id=id)
        if Hub.objects.filter(nome_hub=nome_hub).exclude(id=hub.id).exists():
            messages.error(request, "Essa Hub já existe")
            return redirect('administrador:gerenciarHubs')

        if nome_hub:
            hub.nome_hub = nome_hub
    
        if foto_hub is not None:
            hub.foto_hub = foto_hub

        if descricao_hub:  
            hub.descricao_hub = descricao_hub

        hub.save()
        messages.success(request, "Hub Alterado com sucesso")
        return redirect('administrador:gerenciarHubs')
    
    messages.error(request, "Não foi possivel acessar")
    return redirect('administrador:gerenciarHubs')



@login_required
def deletaHub(request, hubs_id):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')
    hub = Hub.objects.get(id=hubs_id)
    if hub.isActive:
        hub.isActive = False
        hub.save()
        messages.success(request, "Hub Desativado com sucesso!")
    else:
        hub.isActive = True
        hub.save()
        messages.success(request, "Hub Ativado com sucesso!")
    return redirect('administrador:gerenciarHubs')



@login_required
def gerenciarSalas(request):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')

    salas_lista = Sala.objects.prefetch_related('imagens', 'hubs').order_by('-isActive', 'nome_sala')
    hubs = Hub.objects.filter(isActive=True).order_by('nome_hub')
    return render(request, "gerenciarSalas.html", {'salas_lista': salas_lista, 'hubs': hubs})


@login_required
def cadastrarSala(request):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')

    if request.method == 'POST':
        nome_sala = request.POST.get('txtNomeSala')
        descricao_recursos = request.POST.get('txtDescricaoRecursos')
        hub_ids = request.POST.getlist('selHub')
        imagens = request.FILES.getlist('fleImagensSala')

        sala = Sala.objects.create(
            nome_sala=nome_sala,
            descricao_recursos=descricao_recursos,
        )
        sala.hubs.set(hub_ids)

        for ordem, imagem in enumerate(imagens):
            SalaImagem.objects.create(sala=sala, imagem=imagem, ordem=ordem)

        messages.success(request, "Sala cadastrada com sucesso")
        return redirect('administrador:cadastrarSala')

    hubs = Hub.objects.filter(isActive=True).order_by('nome_hub')
    return render(request, "cadastrar_salas.html", {'hubs': hubs})


@login_required
def alterarSala(request):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')

    if request.method == 'POST':
        id = request.POST.get('idsala')
        nome_sala = request.POST.get('txtNomeSala')
        descricao_recursos = request.POST.get('txtDescricaoRecursos')
        hub_ids = request.POST.getlist('selHub')
        imagens = request.FILES.getlist('fleImagensSala')

        sala = Sala.objects.get(id=id)

        if nome_sala:
            sala.nome_sala = nome_sala

        if descricao_recursos:
            sala.descricao_recursos = descricao_recursos

        sala.save()
        sala.hubs.set(hub_ids)

        proxima_ordem = sala.imagens.count()
        for i, imagem in enumerate(imagens):
            SalaImagem.objects.create(sala=sala, imagem=imagem, ordem=proxima_ordem + i)

        messages.success(request, "Sala alterada com sucesso")
        return redirect('administrador:gerenciarSalas')

    messages.error(request, "Não foi possivel acessar")
    return redirect('administrador:gerenciarSalas')


@login_required
def deletaSala(request, sala_id):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')

    sala = Sala.objects.get(id=sala_id)
    if sala.isActive:
        sala.isActive = False
        sala.save()
        messages.success(request, "Sala desativada com sucesso!")
    else:
        sala.isActive = True
        sala.save()
        messages.success(request, "Sala ativada com sucesso!")
    return redirect('administrador:gerenciarSalas')


@login_required
def deletaSalaImagem(request, imagem_id):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')

    imagem = SalaImagem.objects.get(id=imagem_id)
    imagem.imagem.delete(save=False)
    imagem.delete()
    messages.success(request, "Imagem removida com sucesso!")
    return redirect('administrador:gerenciarSalas')


@login_required
def cadastrarNoticias(request):
    if not request.user.is_admin:
        messages.error(request, "Acesso negado")
        return redirect('core:home')

    if request.method == 'POST':
        titulo_noticia = request.POST.get('txtTituloNoticia')
        descricao_noticia = request.POST.get('txtDescricaoNoticia')
        fonte = request.POST.get('txtFonte')
        url = request.POST.get('txtUrl')
        imagem_noticia = request.FILES.get('fleImagemNoticia')
        is_home = request.POST.get('chkIsHome') == 'on'

        # CAPTURA O HUB SELECIONADO
        hub_id = request.POST.get('selHub')

        if Noticia.objects.filter(titulo_noticia=titulo_noticia).exists():
            messages.error(request, "Notícia com este título já cadastrada")
            return redirect('administrador:cadastrarNoticias')

        # 1. Cria a Notícia primeiro
        noticia = Noticia.objects.create(
            titulo_noticia=titulo_noticia,
            descricao_noticia=descricao_noticia,
            fonte=fonte,
            url=url if url else None,
            imagem_noticia=imagem_noticia if imagem_noticia else None,
            isHome=is_home,
            isActive=True
        )

        # 2. Se um Hub foi selecionado, cria o vínculo na NoticiaHub
        if hub_id:
            hub_obj = Hub.objects.get(id=hub_id)
            NoticiaHub.objects.create(noticia=noticia, hub=hub_obj)

        messages.success(request, "Notícia cadastrada com sucesso!")
        return redirect('administrador:gerenciarNoticias')

    # Passa os hubs para o select no HTML
    hubs = Hub.objects.filter(isActive=True).order_by('nome_hub')
    return render(request, "cadastrar_noticias.html", {'hubs': hubs})


@login_required
def alterarNoticias(request):
    # Verificação de segurança: Apenas administradores
    if not request.user.is_admin:
        messages.error(request, "Acesso negado")
        return redirect('core:home')

    if request.method == 'POST':
        id_noticia = request.POST.get('idnoticia')
        titulo_noticia = request.POST.get('txtTituloNoticia')
        descricao_noticia = request.POST.get('txtDescricaoNoticia')
        fonte = request.POST.get('txtFonte')
        url = request.POST.get('txtUrl')
        imagem_noticia = request.FILES.get('fleImagemNoticia')
        hub_id = request.POST.get('selHub')  # ID vindo do select

        try:
            noticia = Noticia.objects.get(id=id_noticia)

            # 1. Verificar se o novo título já existe em OUTRA notícia
            if Noticia.objects.filter(titulo_noticia=titulo_noticia).exclude(id=noticia.id).exists():
                messages.error(
                    request, "Já existe outra notícia com este título")
                return redirect('administrador:gerenciarNoticias')

            # 2. Atualizar campos básicos
            noticia.titulo_noticia = titulo_noticia
            noticia.descricao_noticia = descricao_noticia
            noticia.fonte = fonte
            noticia.url = url if url else None

            if imagem_noticia is not None:
                if noticia.imagem_noticia:
                    noticia.imagem_noticia.delete(save=False)
                noticia.imagem_noticia = imagem_noticia

            noticia.save()

            # 3. Gerenciar vínculo na tabela NoticiaHub
            if hub_id:
                # Se selecionou um Hub, cria ou atualiza o vínculo
                hub_obj = Hub.objects.get(id=hub_id)
                NoticiaHub.objects.update_or_create(
                    noticia=noticia,
                    defaults={'hub': hub_obj}
                )
            else:
                # Se selecionou "Nenhum", remove qualquer vínculo existente
                NoticiaHub.objects.filter(noticia=noticia).delete()

            messages.success(
                request, "Notícia e vínculo atualizados com sucesso!")
            return redirect('administrador:gerenciarNoticias')

        except Noticia.DoesNotExist:
            messages.error(request, "Notícia não encontrada")
            return redirect('administrador:gerenciarNoticias')

    return redirect('administrador:gerenciarNoticias')


@login_required
def deletaNoticias(request, noticia_id):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')

    try:
        noticia = Noticia.objects.get(id=noticia_id)

        if noticia.isActive:
            noticia.isActive = False
            noticia.save()
            messages.success(request, "Notícia desativada com sucesso!")
        else:
            noticia.isActive = True
            noticia.save()
            messages.success(request, "Notícia ativada com sucesso!")

        return redirect('administrador:gerenciarNoticias')

    except Noticia.DoesNotExist:
        messages.error(request, "Notícia não encontrada")
        return redirect('administrador:gerenciarNoticias')

@login_required
def gerenciarNoticias(request):
    if (request.user.is_admin != True):
        messages.error(request, "Acesso negado")
        return redirect('core:home')

    noticias_lista = Noticia.objects.all().order_by('-id')
    for noticia in noticias_lista:
        # Busca o vínculo na tabela intermediária
        vinculo = NoticiaHub.objects.filter(
            noticia=noticia).select_related('hub').first()
        if vinculo:
            noticia.nome_hub = vinculo.hub.nome_hub
            # Útil para marcar o select como 'selected' no modal de edição
            noticia.hub_id_atual = vinculo.hub.id
        else:
            noticia.nome_hub = "Geral (Sem Hub)"
            noticia.hub_id_atual = None

    hubs = Hub.objects.filter(isActive=True).order_by('nome_hub')

    context = {
        'noticias_lista': noticias_lista,
        'hubs': hubs,
    }

    return render(request, "gerenciarNoticias.html", context)

from django.db.models import Q
 
 
@login_required
def listar_usuarios(request):
    if not request.user.is_admin:
        messages.error(request, "Acesso negado")
        return redirect('core:home')
 
    tipo = request.GET.get('tipo', '')       # candidato | empresa | '' (todos)
    busca = request.GET.get('busca', '').strip()
 
    usuarios = UsuarioBase.objects.all().order_by('-is_active', 'nome')
 
    if tipo in ('candidato', 'empresa'):
        usuarios = usuarios.filter(tipo=tipo)
 
    if busca:
        usuarios = usuarios.filter(
            Q(nome__icontains=busca) | Q(email__icontains=busca)
        )
 
    context = {
        'usuarios': usuarios,
        'tipo_selecionado': tipo,
        'busca': busca,
    }
    return render(request, "listar_usuarios.html", context)
 
 
@login_required
def detalhe_usuario(request, usuario_id):
    if not request.user.is_admin:
        messages.error(request, "Acesso negado")
        return redirect('core:home')
 
    usuario_base = UsuarioBase.objects.get(id=usuario_id)
 
    # Tenta buscar perfil estendido (candidato)
    try:
        perfil = usuario_base.usuario
    except Exception:
        perfil = None
 
    context = {
        'usuario_base': usuario_base,
        'perfil': perfil,
    }
    return render(request, "detalhe_usuario.html", context)
 
 
@login_required
def desativar_usuario(request, usuario_id):
    if not request.user.is_admin:
        messages.error(request, "Acesso negado")
        return redirect('core:home')
 
    usuario = UsuarioBase.objects.get(id=usuario_id)
 
    if usuario.is_admin:
        messages.error(request, "Não é possível desativar um administrador.")
        return redirect('administrador:listar_usuarios')
 
    if usuario.is_active:
        usuario.is_active = False
        usuario.save()
        messages.success(request, f"Usuário '{usuario.nome}' desativado com sucesso!")
    else:
        usuario.is_active = True
        usuario.save()
        messages.success(request, f"Usuário '{usuario.nome}' reativado com sucesso!")
 
    return redirect('administrador:listar_usuarios')

from django.db.models import Q
 
 
@login_required
def listar_usuarios(request):
    if not request.user.is_admin:
        messages.error(request, "Acesso negado")
        return redirect('core:home')
 
    tipo = request.GET.get('tipo', '')       # candidato | empresa | '' (todos)
    busca = request.GET.get('busca', '').strip()
 
    usuarios = UsuarioBase.objects.all().order_by('-is_active', 'nome')
 
    if tipo in ('candidato', 'empresa'):
        usuarios = usuarios.filter(tipo=tipo)
 
    if busca:
        usuarios = usuarios.filter(
            Q(nome__icontains=busca) | Q(email__icontains=busca)
        )
 
    context = {
        'usuarios': usuarios,
        'tipo_selecionado': tipo,
        'busca': busca,
    }
    return render(request, "listar_usuarios.html", context)
 
 
@login_required
def detalhe_usuario(request, usuario_id):
    if not request.user.is_admin:
        messages.error(request, "Acesso negado")
        return redirect('core:home')
 
    usuario_base = UsuarioBase.objects.get(id=usuario_id)
 
    # Tenta buscar perfil estendido (candidato)
    try:
        perfil = usuario_base.usuario
    except Exception:
        perfil = None
 
    context = {
        'usuario_base': usuario_base,
        'perfil': perfil,
    }
    return render(request, "detalhe_usuario.html", context)
 
 
@login_required
def desativar_usuario(request, usuario_id):
    if not request.user.is_admin:
        messages.error(request, "Acesso negado")
        return redirect('core:home')
 
    usuario = UsuarioBase.objects.get(id=usuario_id)
 
    if usuario.is_admin:
        messages.error(request, "Não é possível desativar um administrador.")
        return redirect('administrador:listar_usuarios')
 
    if usuario.is_active:
        usuario.is_active = False
        usuario.save()
        messages.success(request, f"Usuário '{usuario.nome}' desativado com sucesso!")
    else:
        usuario.is_active = True
        usuario.save()
        messages.success(request, f"Usuário '{usuario.nome}' reativado com sucesso!")
 
    return redirect('administrador:listar_usuarios')
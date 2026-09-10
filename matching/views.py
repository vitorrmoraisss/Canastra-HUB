# matching/views.py
import math
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core.models import Usuario, InteresseCompra
from vagas.models import Vagas
from empresa.models import Empresa, EmpresaHub
from .models import MatchScore, ProdutoMatch

logger = logging.getLogger(__name__)

_ERRO_PROIBIDO = {"erro": "Acesso negado."}


def _pode_ver_usuario(request, usuario_pk) -> bool:
    """Um candidato só enxerga os próprios matches; staff enxerga todos."""
    if request.user.is_staff:
        return True
    return Usuario.objects.filter(pk=usuario_pk, user=request.user).exists()


def _pode_ver_vaga(request, vaga) -> bool:
    """O ranking de candidatos de uma vaga é restrito à empresa dona da vaga."""
    if request.user.is_staff:
        return True
    return Empresa.objects.filter(pk=vaga.empresa_id, user=request.user).exists()


@login_required
@require_GET
def candidatos_para_vaga(request, vaga_id):
    page = _parse_int(request.GET.get("page"), default=1, min_val=1, max_val=100_000)
    page_size = _parse_int(request.GET.get("page_size"), default=20, min_val=1, max_val=100)

    if page is None or page_size is None:
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)

    vaga = Vagas.objects.filter(pk=vaga_id).only("pk", "empresa_id").first()
    if vaga is None:
        return JsonResponse({"erro": "Vaga não encontrada."}, status=404)

    if not _pode_ver_vaga(request, vaga):
        return JsonResponse(_ERRO_PROIBIDO, status=403)

    qs = (
        MatchScore.objects
        .filter(vaga_id=vaga_id)
        .order_by('-score')
        .select_related('usuario__user')
    )
    total = qs.count()
    offset = (page - 1) * page_size
    resultados = qs[offset: offset + page_size]

    return JsonResponse({
        "total": total,
        "page": page,
        "pages": math.ceil(total / page_size) if total else 0,
        "resultados": [
            {
                "usuario_id": r.usuario_id,
                "nome": r.usuario.user.nome,
                "score": r.score,
                "breakdown": r.breakdown,
            }
            for r in resultados
        ],
    })


@login_required
@require_GET
def vagas_para_usuario(request, usuario_pk):
    page = _parse_int(request.GET.get("page"), default=1, min_val=1, max_val=100_000)
    page_size = _parse_int(request.GET.get("page_size"), default=20, min_val=1, max_val=100)

    if page is None or page_size is None:
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)

    if not Usuario.objects.filter(pk=usuario_pk).exists():
        return JsonResponse({"erro": "Candidato não encontrado."}, status=404)

    if not _pode_ver_usuario(request, usuario_pk):
        return JsonResponse(_ERRO_PROIBIDO, status=403)

    qs = (
        MatchScore.objects
        .filter(usuario_id=usuario_pk)
        .order_by('-score')
        .select_related('vaga__empresa')
    )
    total = qs.count()
    offset = (page - 1) * page_size
    resultados = qs[offset: offset + page_size]

    return JsonResponse({
        "total": total,
        "page": page,
        "pages": math.ceil(total / page_size) if total else 0,
        "resultados": [
            {
                "vaga_id": r.vaga_id,
                "cargo": r.vaga.cargo_vaga,
                "empresa": r.vaga.empresa.nomefantasia if r.vaga.empresa else "",
                "score": r.score,
                "breakdown": r.breakdown,
            }
            for r in resultados
        ],
    })


def _hubs_da_empresa(empresa):
    return list(
        EmpresaHub.objects
        .filter(empresa=empresa, hub__isActive=True)
        .select_related("hub")
        .values_list("hub__id", "hub__nome_hub")
    )


def _serialize_produto_match(match: ProdutoMatch) -> dict:
    produto = match.produto
    empresa = produto.empresa
    hubs = _hubs_da_empresa(empresa)
    return {
        "match_id": match.pk,
        "score": match.score,
        "breakdown": match.breakdown,
        "produto": {
            "id": produto.pk,
            "nome": produto.nome_produto,
            "categoria": produto.categoria_produto,
            "descricao": produto.descricao_produto,
            "preco": produto.preco_produto,
        },
        "empresa": {
            "id": empresa.pk,
            "nome": empresa.nomefantasia,
        },
        "hubs": [{"id": hub_id, "nome": hub_nome} for hub_id, hub_nome in hubs],
    }


@login_required
@require_GET
def produtos_para_interesse(request, interesse_id):
    page = _parse_int(request.GET.get("page"), default=1, min_val=1, max_val=100_000)
    page_size = _parse_int(request.GET.get("page_size"), default=20, min_val=1, max_val=100)

    if page is None or page_size is None:
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)

    interesse = (
        InteresseCompra.objects
        .filter(pk=interesse_id, isActive=True)
        .only("pk", "usuario_id")
        .first()
    )
    if interesse is None:
        return JsonResponse({"erro": "Interesse de compra não encontrado."}, status=404)

    if not _pode_ver_usuario(request, interesse.usuario_id):
        return JsonResponse(_ERRO_PROIBIDO, status=403)

    qs = (
        ProdutoMatch.objects
        .filter(
            interesse_id=interesse_id,
            produto__isActive=True,
            produto__empresa__user__is_active=True,
        )
        .order_by('-score')
        .select_related('produto__empresa')
    )
    total = qs.count()
    offset = (page - 1) * page_size
    resultados = qs[offset: offset + page_size]

    return JsonResponse({
        "total": total,
        "page": page,
        "pages": math.ceil(total / page_size) if total else 0,
        "resultados": [_serialize_produto_match(m) for m in resultados],
    })


@login_required
@require_GET
def matches_para_usuario(request, usuario_pk):
    page = _parse_int(request.GET.get("page"), default=1, min_val=1, max_val=100_000)
    page_size = _parse_int(request.GET.get("page_size"), default=20, min_val=1, max_val=100)

    if page is None or page_size is None:
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)

    if not Usuario.objects.filter(pk=usuario_pk).exists():
        return JsonResponse({"erro": "Usuário não encontrado."}, status=404)

    if not _pode_ver_usuario(request, usuario_pk):
        return JsonResponse(_ERRO_PROIBIDO, status=403)

    qs = (
        ProdutoMatch.objects
        .filter(
            interesse__usuario_id=usuario_pk,
            interesse__isActive=True,
            produto__isActive=True,
            produto__empresa__user__is_active=True,
        )
        .order_by('-score')
        .select_related('produto__empresa', 'interesse')
    )
    total = qs.count()
    offset = (page - 1) * page_size
    resultados = qs[offset: offset + page_size]

    return JsonResponse({
        "total": total,
        "page": page,
        "pages": math.ceil(total / page_size) if total else 0,
        "resultados": [
            {**_serialize_produto_match(m), "interesse_id": m.interesse_id}
            for m in resultados
        ],
    })


def _parse_int(value, *, default: int, min_val: int, max_val: int):
    if value is None:
        return default
    try:
        v = int(value)
        return v if min_val <= v <= max_val else None
    except (ValueError, TypeError):
        return None

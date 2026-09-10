# matching/signals.py
import logging

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.models import Usuario, ExperienciaProfissional, InteresseCompra, Hub
from vagas.models import Vagas
from empresa.models import EmpresaHub, Produto
from matching.matcher import JobModel, ResumeModel
from .service import get_matcher
from .text_builders import build_resume_text, build_job_text

logger = logging.getLogger(__name__)


def _upsert_scores_for_usuario(usuario):
    """Computa composite_score do usuario contra todas as vagas e faz bulk upsert."""
    from .models import MatchScore
    from .scoring import composite_score

    matcher = get_matcher()
    vagas = list(Vagas.objects.all())
    if not vagas:
        return

    records = []
    for vaga in vagas:
        try:
            result = composite_score(usuario, vaga, matcher.model)
            records.append(MatchScore(
                usuario=usuario,
                vaga=vaga,
                score=result['score'],
                breakdown=result['breakdown'],
            ))
        except Exception:
            logger.exception("Erro ao calcular score usuario=%s vaga=%s", usuario.pk, vaga.pk)

    if records:
        MatchScore.objects.bulk_create(
            records,
            update_conflicts=True,
            unique_fields=['usuario', 'vaga'],
            # updated_at must be explicit: auto_now=True is not set by bulk_create
            update_fields=['score', 'breakdown', 'updated_at'],
        )


def _upsert_hub_scores_for_usuario(usuario):
    """Computa composite_score_hub do usuario contra todos os hubs ativos e faz bulk upsert."""
    from .models import HubMatchScore
    from .scoring import composite_score_hub

    if not usuario.user.is_active:
        HubMatchScore.objects.filter(usuario=usuario).delete()
        return

    matcher = get_matcher()
    hubs = list(Hub.objects.filter(isActive=True))
    if not hubs:
        return

    records = []
    for hub in hubs:
        try:
            result = composite_score_hub(usuario, hub, matcher.model)
            records.append(HubMatchScore(
                usuario=usuario,
                hub=hub,
                score=result['score'],
                breakdown=result['breakdown'],
            ))
        except Exception:
            logger.exception("Erro ao calcular score hub usuario=%s hub=%s", usuario.pk, hub.pk)

    if records:
        HubMatchScore.objects.bulk_create(
            records,
            update_conflicts=True,
            unique_fields=['usuario', 'hub'],
            update_fields=['score', 'breakdown', 'updated_at'],
        )


def _upsert_hub_scores_for_hub(hub):
    """Computa composite_score_hub de todos os usuarios contra o hub e faz bulk upsert."""
    from .models import HubMatchScore
    from .scoring import composite_score_hub

    HubMatchScore.objects.filter(hub=hub).delete()
    if not hub.isActive:
        return

    matcher = get_matcher()
    usuarios = list(Usuario.objects.filter(user__is_active=True).select_related('user'))
    if not usuarios:
        return

    records = []
    for usuario in usuarios:
        try:
            result = composite_score_hub(usuario, hub, matcher.model)
            records.append(HubMatchScore(
                usuario=usuario,
                hub=hub,
                score=result['score'],
                breakdown=result['breakdown'],
            ))
        except Exception:
            logger.exception("Erro ao calcular score hub usuario=%s hub=%s", usuario.pk, hub.pk)

    if records:
        HubMatchScore.objects.bulk_create(records)


def _upsert_scores_for_vaga(vaga):
    """Computa composite_score de todos os usuarios contra a vaga e faz bulk upsert."""
    from .models import MatchScore
    from .scoring import composite_score

    matcher = get_matcher()
    usuarios = list(Usuario.objects.all())
    if not usuarios:
        return

    records = []
    for usuario in usuarios:
        try:
            result = composite_score(usuario, vaga, matcher.model)
            records.append(MatchScore(
                usuario=usuario,
                vaga=vaga,
                score=result['score'],
                breakdown=result['breakdown'],
            ))
        except Exception:
            logger.exception("Erro ao calcular score usuario=%s vaga=%s", usuario.pk, vaga.pk)

    if records:
        MatchScore.objects.bulk_create(
            records,
            update_conflicts=True,
            unique_fields=['usuario', 'vaga'],
            # updated_at must be explicit: auto_now=True is not set by bulk_create
            update_fields=['score', 'breakdown', 'updated_at'],
        )


@receiver(post_save, sender=Usuario, dispatch_uid="matching.sync_usuario")
def sync_usuario(sender, instance, **kwargs):
    try:
        get_matcher().update_resume(
            ResumeModel(
                text=build_resume_text(instance),
                candidate_name=instance.user.nome,
                candidate_id=str(instance.pk),
            )
        )
    except Exception:
        logger.exception("Erro ao sincronizar candidato %s com o JobMatcher", instance.pk)

    try:
        _upsert_scores_for_usuario(instance)
    except Exception:
        logger.exception("Erro ao persistir MatchScore para usuario %s", instance.pk)

    try:
        _upsert_hub_scores_for_usuario(instance)
    except Exception:
        logger.exception("Erro ao persistir HubMatchScore para usuario %s", instance.pk)


@receiver(post_save, sender=ExperienciaProfissional, dispatch_uid="matching.sync_experiencia")
def sync_experiencia(sender, instance, **kwargs):
    try:
        _upsert_scores_for_usuario(instance.usuario)
    except Exception:
        logger.exception("Erro ao persistir MatchScore para experiencia do usuario %s", instance.usuario_id)


@receiver(post_save, sender=Hub, dispatch_uid="matching.sync_hub")
def sync_hub(sender, instance, **kwargs):
    try:
        _upsert_hub_scores_for_hub(instance)
    except Exception:
        logger.exception("Erro ao persistir HubMatchScore para hub %s", instance.pk)


@receiver(post_save, sender=Vagas, dispatch_uid="matching.sync_vaga")
def sync_vaga(sender, instance, **kwargs):
    try:
        get_matcher().update_job(
            JobModel(
                text=build_job_text(instance),
                job_title=instance.cargo_vaga or "",
                company=instance.empresa.nomefantasia if instance.empresa else "",
                job_id=str(instance.id),
            )
        )
    except Exception:
        logger.exception("Erro ao sincronizar vaga %s com o JobMatcher", instance.id)

    try:
        _upsert_scores_for_vaga(instance)
    except Exception:
        logger.exception("Erro ao persistir MatchScore para vaga %s", instance.pk)


def _interesse_esta_ativo(interesse) -> bool:
    return bool(interesse.isActive)


def _produto_esta_ativo(produto) -> bool:
    """Produto só participa do Match se ele, a empresa e o usuário-empresa estiverem ativos."""
    return bool(produto.isActive and produto.empresa and produto.empresa.user.is_active)


def _upsert_matches_for_interesse(interesse):
    """Recalcula os ProdutoMatch de um interesse de compra contra todos os produtos ativos."""
    from .models import ProdutoMatch
    from .scoring import composite_score_produto

    ProdutoMatch.objects.filter(interesse=interesse).delete()

    if not _interesse_esta_ativo(interesse):
        return

    matcher = get_matcher()
    produtos = Produto.objects.filter(isActive=True, empresa__user__is_active=True).select_related("empresa")
    if not produtos:
        return

    records = []
    for produto in produtos:
        try:
            result = composite_score_produto(interesse, produto, matcher.model)
        except Exception:
            logger.exception("Erro ao calcular score interesse=%s produto=%s", interesse.pk, produto.pk)
            continue
        if result["score"] < settings.PRODUCT_MATCH_THRESHOLD:
            continue
        records.append(ProdutoMatch(
            interesse=interesse,
            produto=produto,
            score=result["score"],
            breakdown=result["breakdown"],
        ))

    if records:
        ProdutoMatch.objects.bulk_create(records)


def _upsert_matches_for_produto(produto):
    """Recalcula os ProdutoMatch de um produto contra todos os interesses de compra ativos."""
    from .models import ProdutoMatch
    from .scoring import composite_score_produto

    ProdutoMatch.objects.filter(produto=produto).delete()

    if not _produto_esta_ativo(produto):
        return

    matcher = get_matcher()
    interesses = InteresseCompra.objects.filter(isActive=True)
    if not interesses:
        return

    records = []
    for interesse in interesses:
        try:
            result = composite_score_produto(interesse, produto, matcher.model)
        except Exception:
            logger.exception("Erro ao calcular score interesse=%s produto=%s", interesse.pk, produto.pk)
            continue
        if result["score"] < settings.PRODUCT_MATCH_THRESHOLD:
            continue
        records.append(ProdutoMatch(
            interesse=interesse,
            produto=produto,
            score=result["score"],
            breakdown=result["breakdown"],
        ))

    if records:
        ProdutoMatch.objects.bulk_create(records)


@receiver(post_save, sender=InteresseCompra, dispatch_uid="matching.sync_interesse_compra")
def sync_interesse_compra(sender, instance, **kwargs):
    try:
        _upsert_matches_for_interesse(instance)
    except Exception:
        logger.exception("Erro ao persistir ProdutoMatch para interesse %s", instance.pk)
    try:
        _upsert_hub_scores_for_usuario(instance.usuario)
    except Exception:
        logger.exception("Erro ao atualizar HubMatchScore para interesse %s", instance.pk)


def _recalcular_hubs_da_empresa(empresa):
    """Recalcula HubMatchScore de todos os hubs ativos aos quais a empresa pertence."""
    hub_ids = EmpresaHub.objects.filter(empresa=empresa).values_list('hub_id', flat=True)
    for hub in Hub.objects.filter(pk__in=list(hub_ids), isActive=True):
        _upsert_hub_scores_for_hub(hub)


@receiver(post_save, sender=Produto, dispatch_uid="matching.sync_produto")
def sync_produto(sender, instance, **kwargs):
    try:
        _upsert_matches_for_produto(instance)
    except Exception:
        logger.exception("Erro ao persistir ProdutoMatch para produto %s", instance.pk)
    try:
        _recalcular_hubs_da_empresa(instance.empresa)
    except Exception:
        logger.exception("Erro ao atualizar HubMatchScore para produto %s", instance.pk)


@receiver(post_delete, sender=Produto, dispatch_uid="matching.sync_produto_delete")
def sync_produto_delete(sender, instance, **kwargs):
    """ProdutoMatch cai por cascade; o componente produtos_interesse dos hubs não."""
    try:
        _recalcular_hubs_da_empresa(instance.empresa)
    except Exception:
        logger.exception("Erro ao atualizar HubMatchScore ao remover produto %s", instance.pk)


@receiver(post_delete, sender=InteresseCompra, dispatch_uid="matching.sync_interesse_compra_delete")
def sync_interesse_compra_delete(sender, instance, **kwargs):
    try:
        _upsert_hub_scores_for_usuario(instance.usuario)
    except Exception:
        logger.exception("Erro ao atualizar HubMatchScore ao remover interesse %s", instance.pk)


@receiver(post_save, sender=EmpresaHub, dispatch_uid="matching.sync_empresa_hub")
@receiver(post_delete, sender=EmpresaHub, dispatch_uid="matching.sync_empresa_hub_delete")
def sync_empresa_hub(sender, instance, **kwargs):
    """Entrada/saída de empresa em um hub muda o conjunto de produtos ofertados."""
    if instance.hub_id is None:
        return
    try:
        hub = Hub.objects.filter(pk=instance.hub_id, isActive=True).first()
        if hub is not None:
            _upsert_hub_scores_for_hub(hub)
    except Exception:
        logger.exception("Erro ao atualizar HubMatchScore para EmpresaHub %s", instance.pk)


# matching/perfil_usuario.py
"""
Leitura do perfil do usuário no formato normalizado dos models de core:
formação em AcademyGraduation, competências e hobbies como ManyToMany,
experiências/cursos/idiomas como FK reversa e currículo/carta em Attachment.

Usa sempre `.all()` e filtra em Python para aproveitar prefetch_related
quando o chamador o fizer.
"""
from __future__ import annotations

ANEXO_CURRICULO = 'curriculo'
ANEXO_CARTA_APRESENTACAO = 'carta_apresentacao'

# Relações lidas no matching; usar em select_related/prefetch_related ao
# carregar usuários para evitar N queries por vaga/hub.
SELECT_RELATED = ('user', 'objetivo_profissional', 'formacao_academica')
PREFETCH_RELATED = (
    'competencias', 'interesses_hobbies', 'experiencias',
    'cursos_extras', 'idiomas', 'attachments',
)


def formacoes(usuario) -> list:
    """Registros de formação com grau ou curso preenchido."""
    formacao = getattr(usuario, 'formacao_academica', None)
    if formacao is None or not (formacao.grau_escolaridade or formacao.curso_graduacao):
        return []
    return [formacao]


def competencias(usuario, tipo: str) -> list[str]:
    """Nomes das competências do tipo informado ('tecnica' ou 'comportamental')."""
    return [
        c.nome_competencia
        for c in usuario.competencias.all()
        if c.tipo_competencia == tipo and c.nome_competencia
    ]


def competencias_tecnicas_texto(usuario) -> str:
    return ", ".join(competencias(usuario, 'tecnica'))


def hobbies_texto(usuario) -> str:
    return ", ".join(h.nome_hobby for h in usuario.interesses_hobbies.all() if h.nome_hobby)


def experiencias(usuario) -> list:
    return list(usuario.experiencias.all())


def cursos_extras(usuario) -> list:
    return list(usuario.cursos_extras.all())


def idiomas(usuario) -> list:
    return list(usuario.idiomas.all())


def anexo(usuario, descricao: str):
    """Último Attachment com a descrição informada, ou None."""
    anexos = [a for a in usuario.attachments.all() if a.description == descricao and a.file]
    return anexos[-1] if anexos else None

# matching/text_builders.py
from __future__ import annotations

from core.models import Usuario, ExperienciaProfissional
from vagas.models import Vagas, CursoVaga
import fitz

import logging

logger = logging.getLogger(__name__)

def build_resume_text(usuario: Usuario) -> str:
    parts = []

    if usuario.cargo_pretendido:
        parts.append(f"objetivo: {usuario.cargo_pretendido}")
    if usuario.area_interesse:
        parts.append(f"área de interesse: {usuario.area_interesse}")
    if usuario.disponibilidade:
        parts.append(f"disponibilidade: {usuario.disponibilidade}")
    if usuario.remoto:
        parts.append("disponível para trabalho remoto")

    for n in ('1', '2', '3'):
        instituicao = getattr(usuario, f'instituicao_nome{n}')
        grau = getattr(usuario, f'grau_escolaridade{n}')
        curso = getattr(usuario, f'curso_graduacao{n}')
        situacao = getattr(usuario, f'situacao_academica{n}')
        if any([instituicao, grau, curso]):
            linha = " ".join(filter(None, [grau, curso, ("em " + instituicao) if instituicao else None, situacao]))
            parts.append(f"formação: {linha}")

    for n in ('1', '2', '3'):
        tec = getattr(usuario, f'competencias_tecnicas{n}')
        comp = getattr(usuario, f'competencias_comportamentais{n}')
        if tec:
            parts.append(f"competências técnicas: {tec}")
        if comp:
            parts.append(f"competências comportamentais: {comp}")

    try:
        exp = ExperienciaProfissional.objects.get(usuario=usuario)
        for n in ('1', '2', '3'):
            cargo = getattr(exp, f'cargo{n}')
            empresa = getattr(exp, f'nome_empresa{n}')
            if cargo or empresa:
                linha_exp = " em ".join(filter(None, [cargo, empresa]))
                if linha_exp:
                    parts.append(f"experiência: {linha_exp}")
    except ExperienciaProfissional.DoesNotExist:
        logger.info("Nenhuma experiência profissional encontrada para o usuário %s", usuario.pk)
        parts.append("sem experiência profissional registrada")

    if usuario.interesses_hobbies:
        parts.append(f"interesses: {usuario.interesses_hobbies}")

    if usuario.carta_apresentacao:
        parts.append(f"carta de apresentação: {usuario.carta_apresentacao}")

    if usuario.curriculo_pdf:
        curriculo_text = _extract_pdf_text(usuario.curriculo_pdf.path)
        if curriculo_text:
            parts.append(f"currículo: {curriculo_text}")

    return "\n".join(parts)


def build_job_text(vaga: Vagas) -> str:
    parts = []

    if vaga.cargo_vaga:
        parts.append(f"cargo: {vaga.cargo_vaga}")
    if vaga.descricao_vaga:
        parts.append(f"descrição: {vaga.descricao_vaga}")
    if vaga.requisito_vaga:
        parts.append(f"requisitos: {vaga.requisito_vaga}")
    if vaga.local:
        parts.append(f"local: {vaga.local}")

    cursos = CursoVaga.objects.filter(vaga=vaga).values_list('curso', flat=True)
    if cursos:
        parts.append(f"cursos desejados: {', '.join(filter(None, cursos))}")

    try:
        parts.append(f"empresa: {vaga.empresa.nomefantasia}")
        if vaga.empresa.segmento:
            parts.append(f"segmento: {vaga.empresa.segmento}")
    except Exception:
        logger.info("Nenhuma informação de empresa encontrada para a vaga %s", vaga.id)

    return "\n".join(parts)


def _extract_pdf_text(path:str,limite_contraste:float=1.5) -> str:
    try:
        doc = fitz.open(path)
        texto_valido = []

        for num_pagina, pagina in enumerate(doc):
            fundo_r, fundo_g, fundo_b = 1.0, 1.0, 1.0 
            lum_fundo = _calcular_luminancia(fundo_r, fundo_g, fundo_b)
            
            dados_pagina = pagina.get_text("dict")
            
            for bloco in dados_pagina.get("blocks", []):
                if "lines" in bloco:
                    for linha in bloco["lines"]:
                        for span in linha["spans"]:
                            texto = span["text"].strip()
                            if not texto:
                                continue
                                
                            cor_int = span["color"]
                            t_r, t_g, t_b = _extrair_cor_rgb(cor_int)
                            
                            lum_texto = _calcular_luminancia(t_r, t_g, t_b)
                            contraste = _obter_razao_contraste(lum_fundo, lum_texto)
                            
                            if contraste < limite_contraste:
                                print(f"[BLOQUEADO] Texto suspeito oculto na pág {num_pagina+1}: '{texto}' (Contraste: {contraste:.2f}:1)")
                                continue
                            
                            texto_valido.append(span["text"])
                            
        return " ".join(texto_valido)
    except Exception as e:
        logger.exception("Erro ao extrair texto do PDF: %s", e)
        return ""


def _calcular_luminancia(r, g, b):
    """Calcula a luminância relativa de uma cor RGB (valores de 0 a 1)."""
    # Conversão sRGB para linear conforme padrão WCAG
    valores = []
    for c in (r, g, b):
        if c <= 0.03928:
            valores.append(c / 12.92)
        else:
            valores.append(((c + 0.055) / 1.055) ** 2.4)
    
    return 0.2126 * valores[0] + 0.7152 * valores[1] + 0.0722 * valores[2]

def _obter_razao_contraste(lum1, lum2):
    """Calcula a razão de contraste entre duas luminâncias."""
    mais_claro = max(lum1, lum2)
    mais_escuro = min(lum1, lum2)
    return (mais_claro + 0.05) / (mais_escuro + 0.05)

def _extrair_cor_rgb(inteiro_cor):
    """Converte o inteiro de cor do PyMuPDF para tupla RGB (0 a 1)."""
    # PyMuPDF retorna cores em formato int sRGB
    r = ((inteiro_cor >> 16) & 0xFF) / 255.0
    g = ((inteiro_cor >> 8) & 0xFF) / 255.0
    b = (inteiro_cor & 0xFF) / 255.0
    return r, g, b
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
import uuid
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .schemas import ResumeChunk, JobChunk, MatchResult

@dataclass
class ResumeModel:
    text: str
    candidate_name: str
    candidate_id: str
    curriculo_text: str = ""
    carta_apresentacao_text: str = ""

@dataclass
class JobModel:
    text: str
    job_title: str
    company: str
    job_id: Optional[str] = None

class JobMatcher:
    _TYPOGRAPHY_MAP: dict = str.maketrans({
        '“': '"', '”': '"',   # aspas duplas tipográficas
        '‘': "'", '’': "'",   # aspas simples tipográficas
        '–': '-', '—': '-',   # travessão curto e longo
        '•': ' ', '◦': ' ',   # marcadores de lista
        '▪': ' ', '·': ' ',   # quadrado e ponto médio
    })

    # Abreviações comuns em currículos e vagas do mercado brasileiro
    _ABBREVIATIONS: dict[str, str] = {
        r"\bsr\.?": "Sênior",
        r"\bjr\.?": "Júnior",
        r"\bRH\b": "Recursos Humanos",
        r"\bTI\b": "Tecnologia da Informação",
        r"\bML\b": "Machine Learning",
        r"\bBD\b": "Banco de Dados",
        r"\bPJ\b": "Pessoa Jurídica",
        r"\bCLT\b": "Contrato CLT",
        r"\bP&D\b": "Pesquisa e Desenvolvimento",
    }

    _RESUME_HEADERS = [
        "objetivo", "resumo", "summary", "objective",
        "experiência", "experience", "histórico profissional",
        "educação", "education", "formação",
        "habilidades", "skills", "competências",
        "certificações", "certifications",
        "idiomas", "languages",
        "projetos", "projects",
    ]

    _JOB_HEADERS = [
        "descrição", "description", "sobre a vaga", "about the role",
        "responsabilidades", "responsibilities", "atividades",
        "requisitos", "requirements", "qualificações", "qualifications",
        "diferenciais", "nice to have", "benefícios", "benefits",
        "sobre a empresa", "about us", "about the company",
        "stack", "tecnologias", "technologies",
    ]

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        model_name: str = "rufimelo/bert-large-portuguese-cased-sts",
        chunk_size: int = 80,
        chunk_overlap: int = 15,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model = SentenceTransformer(model_name)

        client = (
            chromadb.PersistentClient(path=persist_directory, settings=Settings(anonymized_telemetry=False))
            if persist_directory
            else chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
        )
        self._resumes = client.get_or_create_collection("resumes", metadata={"hnsw:space": "cosine"})
        self._jobs = client.get_or_create_collection("jobs", metadata={"hnsw:space": "cosine"})

    # ── public API ────────────────────────────────────────────────────────────

    def add_resume(self, resume: ResumeModel) -> str:
        candidate_id = resume.candidate_id or str(uuid.uuid4())
        text = self._preprocess(resume.text)
        chunks = [
            ResumeChunk(text=c["text"], section=c["section"],
                        candidate_id=candidate_id, candidate_name=resume.candidate_name)
            for c in self._chunk_text(text, self._RESUME_HEADERS)
        ]
        self._upsert(self._resumes, chunks)
        return candidate_id

    def add_job(self, job: JobModel) -> str:
        job_id = job.job_id or str(uuid.uuid4())
        text = self._preprocess(job.text)
        chunks = [
            JobChunk(text=c["text"], section=c["section"],
                     job_id=job_id, job_title=job.job_title, company=job.company)
            for c in self._chunk_text(text, self._JOB_HEADERS)
        ]
        self._upsert(self._jobs, chunks)
        return job_id

    def update_resume(self, resume: ResumeModel) -> str:
        self._delete_by_field(self._resumes, "candidate_id", resume.candidate_id)
        return self.add_resume(resume)

    def update_job(self, job: JobModel) -> str:
        self._delete_by_field(self._jobs, "job_id", job.job_id)
        return self.add_job(job)

    def match_jobs_for_resume(self, candidate_id: str, top_k: int = 5, min_score: float = 0.0) -> list[MatchResult]:
        chunks = self._get_chunks(self._resumes, "candidate_id", candidate_id)
        if not chunks:
            raise ValueError(f"Candidato '{candidate_id}' não encontrado.")
        return self._match(chunks, self._jobs, "job_id", "job_title", "company", top_k, min_score)

    def match_resumes_for_job(self, job_id: str, top_k: int = 5, min_score: float = 0.0) -> list[MatchResult]:
        chunks = self._get_chunks(self._jobs, "job_id", job_id)
        if not chunks:
            raise ValueError(f"Vaga '{job_id}' não encontrada.")
        return self._match(chunks, self._resumes, "candidate_id", "candidate_name", None, top_k, min_score)

    def stats(self) -> dict:
        return {"resumes": self._resumes.count(), "jobs": self._jobs.count()}

    def match_structured_resumes_for_job(
        self, vaga, top_k: int = 5, min_score: float = 0.0
    ) -> list[MatchResult]:
        """Pipeline de 4 critérios ponderados para rankear candidatos por vaga."""
        from core.models import Usuario
        from .scoring import composite_score

        results = []
        for usuario in Usuario.objects.select_related("user").all():
            sc = composite_score(usuario, vaga, self.model)
            if sc["score"] < min_score:
                continue
            results.append(MatchResult(
                entity_id=str(usuario.pk),
                name=usuario.user.nome,
                score=sc["score"],
                breakdown=sc["breakdown"],
            ))
        return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]

    def match_structured_jobs_for_resume(
        self, usuario, top_k: int = 5, min_score: float = 0.0
    ) -> list[MatchResult]:
        """Pipeline de 4 critérios ponderados para recomendar vagas por candidato."""
        from vagas.models import Vagas
        from .scoring import composite_score

        results = []
        for vaga in Vagas.objects.filter(status="ativa").select_related("empresa"):
            sc = composite_score(usuario, vaga, self.model)
            if sc["score"] < min_score:
                continue
            try:
                company = vaga.empresa.nomefantasia or ""
            except Exception:
                company = ""
            results.append(MatchResult(
                entity_id=str(vaga.pk),
                name=vaga.cargo_vaga or "",
                company=company,
                score=sc["score"],
                breakdown=sc["breakdown"],
            ))
        return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]

    def match_structured_hubs_for_usuario(
        self, usuario, top_k: int = 5, min_score: float = 0.0
    ) -> list[MatchResult]:
        """Ranqueia hubs ativos por afinidade de interesse com o usuário (score 0-100%)."""
        from core.models import Hub
        from .scoring import composite_score_hub

        results = []
        for hub in Hub.objects.filter(isActive=True):
            sc = composite_score_hub(usuario, hub, self.model)
            if sc["score"] < min_score:
                continue
            results.append(MatchResult(
                entity_id=str(hub.pk),
                name=hub.nome_hub,
                score=sc["score"],
                breakdown=sc["breakdown"],
            ))
        return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]

    # ── internals ─────────────────────────────────────────────────────────────

    def _preprocess(self, text: str) -> str:
        """Normaliza texto para melhorar qualidade dos embeddings em PT-BR."""
        # Composição unicode canônica (garante representação consistente de acentos)
        text = unicodedata.normalize("NFC", text)
        # Corrige caracteres tipográficos (aspas, travessões, marcadores)
        text = text.translate(self._TYPOGRAPHY_MAP)
        # Remove URLs e e-mails (ruído para matching semântico)
        text = re.sub(r'https?://\S+|www\.\S+|\S+@\S+\.\S+', '', text)
        # Expande abreviações comuns do mercado de trabalho brasileiro
        for pattern, replacement in self._ABBREVIATIONS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        # Remove caracteres especiais mantendo letras, números, hífens, barras e parênteses
        text = re.sub(r'[^\w\s\-\/\(\)\.,]', ' ', text)
        # Normaliza espaços múltiplos
        return re.sub(r'\s+', ' ', text).strip()

    def _match(self, source_chunks, target, group_key, name_key, extra_key, top_k, min_score):
        texts = [c["text"] for c in source_chunks]
        embeddings = self.model.encode(texts, show_progress_bar=False).tolist()
        n_query = min(top_k * 3, max(target.count(), 1))

        scores: dict[str, list[float]] = {}
        best_chunks: dict[str, list[dict]] = {}
        meta_map: dict[str, dict] = {}

        for emb in embeddings:
            result = target.query(
                query_embeddings=[emb],
                n_results=n_query,
                include=["documents", "metadatas", "distances"],
            )
            for doc, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
                eid = meta[group_key]
                sim = round(1 - dist, 4)
                scores.setdefault(eid, []).append(sim)
                meta_map.setdefault(eid, meta)
                best_chunks.setdefault(eid, []).append({"text": doc, "similarity": sim})

        results = []
        for eid, sims in scores.items():
            avg = round(sum(sims) / len(sims), 4)
            if avg < min_score:
                continue
            top = sorted(best_chunks[eid], key=lambda x: x["similarity"], reverse=True)[:3]
            results.append(MatchResult(
                entity_id=eid,
                name=meta_map[eid].get(name_key, eid),
                company=meta_map[eid].get(extra_key, "") if extra_key else "",
                score=avg,
                top_chunks=top,
            ))

        return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]

    def _upsert(self, collection, chunks: list) -> None:
        docs = [c.text for c in chunks]
        collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=docs,
            metadatas=[c.to_metadata() for c in chunks],
            embeddings=self.model.encode(docs, show_progress_bar=False).tolist(),
        )

    def _delete_by_field(self, collection, field: str, value: str) -> None:
        result = collection.get(where={field: {"$eq": value}}, include=[])
        if result["ids"]:
            collection.delete(ids=result["ids"])

    def _get_chunks(self, collection, field: str, value: str) -> list[dict]:
        result = collection.get(
            where={field: {"$eq": value}},
            include=["documents", "metadatas"],
        )
        return [{"text": doc, "metadata": meta}
                for doc, meta in zip(result["documents"], result["metadatas"])]

    def _chunk_text(self, text: str, headers: list[str]) -> list[dict]:
        chunks = []
        for section_name, section_text in self._detect_sections(text, headers):
            words = section_text.split()
            start = 0
            while start < len(words):
                end = min(start + self.chunk_size, len(words))
                chunk = " ".join(words[start:end]).strip()
                if chunk:
                    chunks.append({"text": chunk, "section": section_name})
                start += self.chunk_size - self.chunk_overlap
        return chunks

    def _detect_sections(self, text: str, headers: list[str]) -> list[tuple[str, str]]:
        pattern = re.compile(
            r"^(?P<header>" + "|".join(re.escape(h) for h in headers) + r")\s*[:\-]?\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        matches = list(pattern.finditer(text))
        if not matches:
            return [("Geral", text.strip())]

        sections = []
        for i, match in enumerate(matches):
            header = match.group("header").capitalize()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if content:
                sections.append((header, content))
        return sections or [("Geral", text.strip())]

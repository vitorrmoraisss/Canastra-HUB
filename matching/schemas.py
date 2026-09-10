from dataclasses import dataclass, field
import uuid


@dataclass
class ResumeChunk:
    text: str
    section: str
    candidate_id: str
    candidate_name: str
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_metadata(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "section": self.section,
            "type": "resume",
        }


@dataclass
class JobChunk:
    text: str
    section: str
    job_id: str
    job_title: str
    company: str
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_metadata(self) -> dict:
        return {
            "job_id": self.job_id,
            "job_title": self.job_title,
            "company": self.company,
            "section": self.section,
            "type": "job",
        }


@dataclass
class MatchResult:
    entity_id: str
    name: str
    company: str = ""
    score: float = 0.0
    top_chunks: list[dict] = field(default_factory=list)
    breakdown: dict = field(default_factory=dict)

    def __str__(self) -> str:
        label = f"{self.name} @ {self.company}" if self.company else self.name
        return (
            f"  [{self.score:.1%}] {label}\n"
            + "\n".join(f"    • {c['text'][:90]}…" for c in self.top_chunks[:2])
        )

from __future__ import annotations

from dataclasses import dataclass

from quati.ai import AIAnalysis, analyze_locally
from quati.domain import JobRecord
from quati.resumes import (
    ResumeDocument,
    create_cover_letter,
    export_docx,
    export_pdf,
    tailor_document,
)


@dataclass(frozen=True, slots=True)
class ApplicationBundle:
    job_id: int
    resume_text: str
    cover_letter: str
    analysis: AIAnalysis
    pdf: bytes
    docx: bytes


def prepare_application(
    job: JobRecord, resume: ResumeDocument, *, tailor: bool = True
) -> ApplicationBundle:
    """Prepara arquivos localmente; não abre nem envia formulários externos."""
    analysis = analyze_locally(job, resume.text)
    resume_text = tailor_document(resume, job, analysis) if tailor else resume.text
    cover_letter = create_cover_letter(resume, job)
    title = f"Currículo — {job.title}"
    return ApplicationBundle(
        job_id=job.id,
        resume_text=resume_text,
        cover_letter=cover_letter,
        analysis=analysis,
        pdf=export_pdf(title, resume_text),
        docx=export_docx(title, resume_text),
    )

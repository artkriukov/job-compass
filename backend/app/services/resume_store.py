import json
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from docx import Document
from pypdf import PdfReader

from app.models import ResumeSnapshot

MAX_RESUME_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".docx", ".md", ".pdf", ".txt"}


class ResumeStorageError(RuntimeError):
    pass


class ResumeValidationError(ValueError):
    pass


def _normalize_text(value: str) -> str:
    paragraphs = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    normalized: list[str] = []
    for paragraph in paragraphs:
        if paragraph or (normalized and normalized[-1]):
            normalized.append(paragraph)
    return "\n".join(normalized).strip()


def _extract_pdf(payload: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(payload))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pypdf exposes several parser-specific exceptions
        raise ResumeValidationError("Не удалось прочитать PDF-файл") from exc


def _extract_docx(payload: bytes) -> str:
    try:
        document = Document(BytesIO(payload))
    except Exception as exc:  # python-docx wraps ZIP and XML parser errors
        raise ResumeValidationError("Не удалось прочитать DOCX-файл") from exc
    return "\n\n".join(paragraph.text for paragraph in document.paragraphs)


def extract_resume_text(filename: str, payload: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ResumeValidationError("Поддерживаются только PDF, DOCX, TXT и MD")
    if not payload:
        raise ResumeValidationError("Файл резюме пуст")
    if len(payload) > MAX_RESUME_BYTES:
        raise ResumeValidationError("Размер резюме не должен превышать 10 МБ")

    if extension == ".pdf":
        extracted = _extract_pdf(payload)
    elif extension == ".docx":
        extracted = _extract_docx(payload)
    else:
        try:
            extracted = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ResumeValidationError("Текстовый файл должен быть в кодировке UTF-8") from exc

    normalized = _normalize_text(extracted)
    if len(normalized) < 80:
        raise ResumeValidationError(
            "В резюме извлечено слишком мало текста. Проверьте файл или загрузите DOCX"
        )
    return normalized


class ResumeStore:
    def __init__(self, data_dir: Path | None) -> None:
        self.data_dir = data_dir

    @property
    def metadata_path(self) -> Path:
        if not self.data_dir:
            raise ResumeStorageError("CAREER_OPS_DATA_DIR не настроен")
        return self.data_dir / "data/resume-upload.json"

    def load(self) -> ResumeSnapshot:
        path = self.metadata_path
        if not path.exists():
            return ResumeSnapshot.empty()
        try:
            return ResumeSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ResumeStorageError("Не удалось прочитать сведения о резюме") from exc

    def save(self, *, filename: str, content_type: str | None, payload: bytes) -> ResumeSnapshot:
        if not self.data_dir:
            raise ResumeStorageError("CAREER_OPS_DATA_DIR не настроен")

        safe_name = Path(filename).name
        text = extract_resume_text(safe_name, payload)
        document_id = uuid4().hex
        documents_dir = self.data_dir / "documents"
        documents_dir.mkdir(parents=True, exist_ok=True)
        source_path = documents_dir / (
            f"resume-{document_id}-source{Path(safe_name).suffix.lower()}"
        )
        text_path = documents_dir / f"resume-{document_id}.txt"

        try:
            source_path.write_bytes(payload)
            text_path.write_text(text, encoding="utf-8")
            snapshot = ResumeSnapshot(
                uploaded=True,
                original_filename=safe_name,
                content_type=content_type,
                size_bytes=len(payload),
                extracted_characters=len(text),
                preview=text[:4000],
                uploaded_at=datetime.now(UTC),
            )
            metadata_path = self.metadata_path
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = metadata_path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(metadata_path)
        except OSError as exc:
            raise ResumeStorageError("Не удалось сохранить резюме") from exc

        return snapshot

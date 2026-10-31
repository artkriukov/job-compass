import json
import subprocess
from pathlib import Path

import httpx
import pytest

from app.models import CompatibilityRequest, Vacancy
from app.services.career_ops import CareerOpsProvider


def make_root(tmp_path: Path) -> Path:
    (tmp_path / "modes").mkdir()
    (tmp_path / ".agents/skills/career-ops").mkdir(parents=True)
    (tmp_path / "AGENTS.md").write_text("# agents")
    (tmp_path / "doctor.mjs").write_text("")
    (tmp_path / ".agents/skills/career-ops/SKILL.md").write_text("# skill")
    return tmp_path


def make_provider(tmp_path: Path) -> CareerOpsProvider:
    return CareerOpsProvider(
        project_root=make_root(tmp_path),
        data_dir=tmp_path / "user-data",
        codex_bin="codex",
        node_bin="node",
        doctor_timeout_seconds=5,
        analysis_timeout_seconds=60,
        quick_model="gpt-6-luna",
        groq_api_key=None,
        groq_model="openai/gpt-oss-120b",
    )


def test_health_reports_onboarding_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = make_provider(tmp_path)
    monkeypatch.setattr("app.services.career_ops.shutil.which", lambda _name: "/bin/tool")

    def fake_run(command, **kwargs):  # noqa: ANN001
        assert command == ["node", "doctor.mjs", "--json"]
        assert kwargs["env"]["CAREER_OPS_DATA_DIR"] == str(tmp_path / "user-data")
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "onboardingNeeded": True,
                    "missing": ["cv.md", "config/profile.yml"],
                    "warnings": [],
                }
            ),
            "",
        )

    monkeypatch.setattr("app.services.career_ops.subprocess.run", fake_run)

    health = provider.health()

    assert health.configured is True
    assert health.installed is True
    assert health.codex_available is True
    assert health.onboarding_needed is True
    assert health.missing == ["cv.md", "config/profile.yml"]


def test_health_handles_unconfigured_provider() -> None:
    provider = CareerOpsProvider(
        project_root=None,
        data_dir=None,
        codex_bin="missing-codex",
        node_bin="missing-node",
        doctor_timeout_seconds=5,
        analysis_timeout_seconds=60,
        quick_model="gpt-6-luna",
        groq_api_key=None,
        groq_model="openai/gpt-oss-120b",
    )

    health = provider.health()

    assert health.configured is False
    assert health.installed is False
    assert health.onboarding_needed is None


def test_health_handles_invalid_doctor_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = make_provider(tmp_path)
    monkeypatch.setattr("app.services.career_ops.shutil.which", lambda _name: "/bin/tool")
    monkeypatch.setattr(
        "app.services.career_ops.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "not-json", ""),
    )

    health = provider.health()

    assert health.onboarding_needed is None
    assert health.warnings == ["Career Ops doctor вернул некорректный JSON"]


def make_request() -> CompatibilityRequest:
    return CompatibilityRequest(
        vacancy=Vacancy(
            title="Backend developer",
            company="Example",
            location="Remote",
            url="https://example.com/jobs/1",
            score=90,
            reason="совпадает роль",
            source_site="https://example.com/jobs",
        ),
        target_roles=["Backend developer"],
        mode="full",
    )


def test_evaluate_runs_codex_and_parses_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = make_provider(tmp_path)
    documents = tmp_path / "user-data/documents"
    documents.mkdir(parents=True)
    (documents / "resume-one.txt").write_text("Real resume text")
    metadata = tmp_path / "user-data/data/resume-upload.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("{}")
    monkeypatch.setattr("app.services.career_ops.shutil.which", lambda _name: "/bin/tool")

    def fake_run(command, **kwargs):  # noqa: ANN001
        if command[1] == "browser-extract.mjs":
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({
                    "url": "https://example.com/jobs/1",
                    "title": "Backend developer",
                    "text": "Backend developer. Full vacancy description. Apply now. " * 3,
                }),
                "",
            )
        assert command[:2] == ["codex", "exec"]
        assert str(tmp_path / "user-data") in command
        assert "UNTRUSTED VACANCY DATA" in kwargs["input"]
        assert "Full vacancy description" in kwargs["input"]
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(json.dumps({
            "score": 4.2,
            "decision": "apply",
            "summary": "Сильное совпадение",
            "strengths": ["Python"],
            "gaps": [],
            "improvements": ["Уточнить масштаб"],
            "risks": [],
            "keywords": ["FastAPI"],
            "report_path": "reports/001-example.md",
        }))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.services.career_ops.subprocess.run", fake_run)

    result = provider.evaluate(make_request())

    assert result.score == 4.2
    assert result.decision == "apply"
    assert result.report_path == "reports/001-example.md"


def test_evaluate_requires_uploaded_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = make_provider(tmp_path)
    monkeypatch.setattr("app.services.career_ops.shutil.which", lambda _name: "/bin/tool")

    with pytest.raises(RuntimeError, match="Сначала загрузите резюме"):
        provider.evaluate(make_request())


def test_extract_vacancy_page_returns_none_on_browser_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = make_provider(tmp_path)
    monkeypatch.setattr(
        "app.services.career_ops.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "browser failed"),
    )

    assert provider._extract_vacancy_page("https://example.com/jobs/1") is None


def test_compact_job_text_removes_application_form_and_related_jobs() -> None:
    description = "Описание вакансии. " * 40
    text = f"{description}\nОТКЛИК НА ВАКАНСИЮ\nИмя\nРезюме\nЕЩЁ ВАРИАНТЫ"

    compact = CareerOpsProvider._compact_job_text(text)

    assert "Описание вакансии" in compact
    assert "ОТКЛИК НА ВАКАНСИЮ" not in compact


def test_quick_evaluation_uses_small_model_and_persistent_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = make_provider(tmp_path)
    documents = tmp_path / "user-data/documents"
    documents.mkdir(parents=True)
    (documents / "resume-one.txt").write_text("Python and FastAPI production experience")
    metadata = tmp_path / "user-data/data/resume-upload.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("{}")
    monkeypatch.setattr("app.services.career_ops.shutil.which", lambda _name: "/bin/tool")
    codex_calls = 0

    def fake_run(command, **kwargs):  # noqa: ANN001
        nonlocal codex_calls
        if command[1] == "browser-extract.mjs":
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({
                    "url": "https://example.com/jobs/1",
                    "title": "Backend developer",
                    "text": "Backend developer. Python and FastAPI required. Apply now. " * 3,
                }),
                "",
            )
        codex_calls += 1
        assert command[command.index("--model") + 1] == "gpt-6-luna"
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert "не исследуй компанию" in kwargs["input"]
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(json.dumps({
            "score": 4.4,
            "decision": "apply",
            "summary": "Хорошее совпадение",
            "strengths": ["Python"],
            "gaps": [],
            "improvements": [],
            "risks": [],
            "keywords": ["FastAPI"],
            "report_path": None,
        }))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.services.career_ops.subprocess.run", fake_run)
    request = make_request().model_copy(update={"mode": "quick"})

    first = provider.evaluate(request)
    second = provider.evaluate(request)

    assert first.score == second.score == 4.4
    assert codex_calls == 1
    assert list((tmp_path / "user-data/cache/compatibility").glob("*.json"))
    reports = provider.list_reports()
    assert len(reports) == 1
    assert reports[0].vacancy.title == "Backend developer"
    assert reports[0].mode == "quick"
    assert reports[0].result.score == 4.4


def test_list_reports_returns_empty_history(tmp_path: Path) -> None:
    provider = make_provider(tmp_path)

    assert provider.list_reports() == []


def test_list_reports_imports_existing_career_ops_markdown(tmp_path: Path) -> None:
    provider = make_provider(tmp_path)
    reports_dir = tmp_path / "user-data/reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "001-example-2026-10-30.md").write_text(
        """# Оценка: Example — Backend developer

**Date:** 2026-10-30
**URL:** https://example.com/jobs/1
**Score:** 3.8/5

## Machine Summary
Полный сохранённый отчёт.
""",
        encoding="utf-8",
    )

    reports = provider.list_reports()

    assert len(reports) == 1
    assert reports[0].vacancy.title == "Backend developer"
    assert reports[0].result.score == 3.8
    assert reports[0].result.decision == "consider"
    assert reports[0].content and "Machine Summary" in reports[0].content


def test_quick_evaluation_can_use_groq(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = make_provider(tmp_path)
    provider.groq_api_key = "test-key"
    result_payload = {
        "score": 3.6,
        "decision": "consider",
        "summary": "Частичное совпадение",
        "strengths": ["Python"],
        "gaps": [],
        "improvements": [],
        "risks": [],
        "keywords": ["API"],
        "report_path": None,
    }

    def fake_post(url, **kwargs):  # noqa: ANN001
        assert url == "https://api.groq.com/openai/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert kwargs["json"]["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(result_payload)}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.services.career_ops.httpx.post", fake_post)

    result = provider._evaluate_quick_with_groq("prompt")

    assert result.decision == "consider"

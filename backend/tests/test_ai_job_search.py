import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from app.models import SearchRequest
from app.services.ai_job_search import AiJobSearchError, AiJobSearchProvider


def make_root(tmp_path: Path) -> Path:
    (tmp_path / ".claude/skills/job-scraper").mkdir(parents=True)
    (tmp_path / ".claude/skills/job-scraper/SKILL.md").write_text("# scraper")
    (tmp_path / "AGENTS.md").write_text("# agents")
    return tmp_path


def make_provider(tmp_path: Path) -> AiJobSearchProvider:
    return AiJobSearchProvider(
        root=make_root(tmp_path),
        codex_bin="codex",
        timeout_seconds=30,
        max_results=10,
    )


def test_provider_readiness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(tmp_path)
    monkeypatch.setattr("app.services.ai_job_search.shutil.which", lambda _name: "/bin/codex")

    assert provider.is_ready()


def test_provider_parses_structured_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = make_provider(tmp_path)
    request = SearchRequest(sites=["https://example.com/jobs"], role="Python developer")

    def fake_run(command, **_kwargs):  # noqa: ANN001
        result_path = Path(command[command.index("--output-last-message") + 1])
        result_path.write_text(
            json.dumps(
                {
                    "vacancies": [
                        {
                            "title": "Python Developer",
                            "company": "Example",
                            "location": "Remote",
                            "url": "https://example.com/jobs/1",
                            "score": 91,
                            "reason": "role match",
                            "source_site": "https://example.com/jobs",
                        }
                    ],
                    "warnings": [],
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.services.ai_job_search.subprocess.run", fake_run)

    vacancies, warnings = asyncio.run(provider.search(request))

    assert vacancies[0].score == 91
    assert warnings == []


def test_provider_reports_codex_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(tmp_path)
    request = SearchRequest(sites=["https://example.com/jobs"], role="Developer")
    monkeypatch.setattr(
        "app.services.ai_job_search.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 2, "", "failed"),
    )

    with pytest.raises(AiJobSearchError, match="failed"):
        provider._run(request)


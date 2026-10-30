import json
import subprocess
from pathlib import Path

import pytest

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

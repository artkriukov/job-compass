import json
import os
import shutil
import subprocess
from pathlib import Path

from app.models import CareerOpsHealth


class CareerOpsProvider:
    def __init__(
        self,
        *,
        project_root: Path | None,
        data_dir: Path | None,
        codex_bin: str,
        node_bin: str,
        doctor_timeout_seconds: int,
    ) -> None:
        self.project_root = project_root
        self.data_dir = data_dir
        self.codex_bin = codex_bin
        self.node_bin = node_bin
        self.doctor_timeout_seconds = doctor_timeout_seconds

    def is_installed(self) -> bool:
        if not self.project_root:
            return False
        return all(
            path.exists()
            for path in (
                self.project_root / "AGENTS.md",
                self.project_root / "modes",
                self.project_root / "doctor.mjs",
                self.project_root / ".agents/skills/career-ops/SKILL.md",
            )
        ) and shutil.which(self.node_bin) is not None

    def codex_available(self) -> bool:
        return shutil.which(self.codex_bin) is not None

    def health(self) -> CareerOpsHealth:
        configured = self.project_root is not None
        installed = self.is_installed()
        codex_available = self.codex_available()
        if not installed or not self.project_root:
            return CareerOpsHealth(
                configured=configured,
                installed=installed,
                codex_available=codex_available,
            )

        environment = os.environ.copy()
        if self.data_dir:
            environment["CAREER_OPS_DATA_DIR"] = str(self.data_dir)

        try:
            completed = subprocess.run(  # noqa: S603
                [self.node_bin, "doctor.mjs", "--json"],
                cwd=self.project_root,
                env=environment,
                text=True,
                capture_output=True,
                timeout=self.doctor_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CareerOpsHealth(
                configured=True,
                installed=True,
                codex_available=codex_available,
                warnings=[f"Не удалось выполнить Career Ops doctor: {exc}"],
            )

        if completed.returncode != 0:
            details = completed.stderr.strip().splitlines()[-1:] or ["неизвестная ошибка"]
            return CareerOpsHealth(
                configured=True,
                installed=True,
                codex_available=codex_available,
                warnings=[f"Career Ops doctor завершился с ошибкой: {details[0]}"],
            )

        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return CareerOpsHealth(
                configured=True,
                installed=True,
                codex_available=codex_available,
                warnings=["Career Ops doctor вернул некорректный JSON"],
            )

        return CareerOpsHealth(
            configured=True,
            installed=True,
            codex_available=codex_available,
            onboarding_needed=bool(result.get("onboardingNeeded", False)),
            missing=[str(item) for item in result.get("missing", [])],
            warnings=[str(item) for item in result.get("warnings", [])],
        )

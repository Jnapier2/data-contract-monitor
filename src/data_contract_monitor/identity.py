from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .release_identity import find_root, verify_release


class IntegrityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    passed: bool
    version: str | None = None
    build_id: str | None = None
    checked_files: int = 0
    errors: list[str] = Field(default_factory=list)


def find_project_root(start: Path | None = None) -> Path | None:
    return find_root((start or Path(__file__)).resolve())


def verify_release_integrity(root: Path | None = None) -> IntegrityResult:
    project_root = root or find_project_root()
    if project_root is None:
        return IntegrityResult(mode="installed-package", passed=True)
    return IntegrityResult.model_validate(verify_release(project_root))

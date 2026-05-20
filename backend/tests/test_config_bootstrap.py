from pathlib import Path
import json

from app.core.config_bootstrap import ensure_runtime_config, write_json_atomic


def test_ensure_runtime_config_copies_templates_without_overwriting_existing(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    example_dir = tmp_path / "example"
    example_dir.mkdir()
    (example_dir / "config.yaml").write_text("app:\n  name: template\n", encoding="utf-8")
    (example_dir / "xianyu_ai_config.json").write_text(
        json.dumps({"enabled": False, "providers": []}),
        encoding="utf-8",
    )

    runtime_dir.mkdir()
    (runtime_dir / "config.yaml").write_text("app:\n  name: local\n", encoding="utf-8")

    result = ensure_runtime_config(
        runtime_dir=runtime_dir,
        example_dir=example_dir,
        legacy_dir=tmp_path / "legacy",
    )

    assert result == runtime_dir.resolve()
    assert (runtime_dir / "config.yaml").read_text(encoding="utf-8") == "app:\n  name: local\n"
    assert json.loads((runtime_dir / "xianyu_ai_config.json").read_text(encoding="utf-8"))["enabled"] is False


def test_ensure_runtime_config_restores_missing_file_from_backup_before_template(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    example_dir = tmp_path / "example"
    runtime_dir.mkdir()
    example_dir.mkdir()
    (example_dir / "xianyu_ai_config.json").write_text(
        json.dumps({"enabled": False, "providers": []}),
        encoding="utf-8",
    )
    (runtime_dir / "xianyu_ai_config.json.bak").write_text(
        json.dumps({"enabled": True, "providers": [{"id": "p1", "api_key": "sk-test"}]}),
        encoding="utf-8",
    )

    ensure_runtime_config(
        runtime_dir=runtime_dir,
        example_dir=example_dir,
        legacy_dir=tmp_path / "legacy",
    )

    restored = json.loads((runtime_dir / "xianyu_ai_config.json").read_text(encoding="utf-8"))
    assert restored["enabled"] is True
    assert restored["providers"][0]["id"] == "p1"


def test_write_json_atomic_creates_stable_backup(tmp_path: Path):
    path = tmp_path / "state.json"

    write_json_atomic(path, {"value": 1})
    write_json_atomic(path, {"value": 2})

    assert json.loads(path.read_text(encoding="utf-8")) == {"value": 2}
    assert json.loads((tmp_path / "state.json.bak").read_text(encoding="utf-8")) == {"value": 2}
    assert not (tmp_path / "state.json.tmp").exists()

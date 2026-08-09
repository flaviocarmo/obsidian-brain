import json
import subprocess

from brainlib import doctor


class _Proc:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


def _fake_run(payload, rc=0):
    def run(cmd, **kwargs):
        if "--version" in cmd:
            return _Proc("Basic Memory version: 0.22.1", rc)
        return _Proc(json.dumps(payload), rc)
    return run


def test_basic_memory_missing_is_fatal(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    c = doctor.check_basic_memory()
    assert not c.ok and c.fatal and "uv tool install basic-memory" in c.detail


def test_basic_memory_present(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/basic-memory")
    monkeypatch.setattr(doctor.subprocess, "run", _fake_run({}))
    c = doctor.check_basic_memory()
    assert c.ok and "0.22.1" in c.detail


def test_project_matches_vault_via_local_path(vault, monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/basic-memory")
    monkeypatch.setattr(doctor.subprocess, "run",
                        _fake_run({"projects": [{"name": "work", "local_path": str(vault),
                                                 "is_default": True}]}))
    c = doctor.check_basic_memory_project(vault)
    assert c.ok and "work" in c.detail


def test_project_matches_legacy_path_key(vault, monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/basic-memory")
    monkeypatch.setattr(doctor.subprocess, "run",
                        _fake_run({"projects": [{"name": "old", "path": str(vault)}]}))
    assert doctor.check_basic_memory_project(vault).ok


def test_project_not_indexing_vault_is_fatal(vault, monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/basic-memory")
    monkeypatch.setattr(doctor.subprocess, "run",
                        _fake_run({"projects": [{"name": "outro", "local_path": "/tmp/x"}]}))
    c = doctor.check_basic_memory_project(vault)
    assert not c.ok and "project add" in c.detail and "outro" in c.detail


def test_broken_json_is_fatal_not_crash(vault, monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/basic-memory")
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: _Proc("nao e json"))
    assert not doctor.check_basic_memory_project(vault).ok


def test_timeout_is_fatal_not_crash(vault, monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/basic-memory")

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("basic-memory", 60)
    monkeypatch.setattr(doctor.subprocess, "run", boom)
    assert not doctor.check_basic_memory_project(vault).ok


def test_hooks_present():
    assert doctor.check_hooks().ok


def test_run_fails_when_basic_memory_absent(vault, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    rc, msg = doctor.run()
    assert rc == 1 and "basic-memory" in msg and "requisito" in msg


def test_run_ok_when_everything_present(vault, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/basic-memory")
    monkeypatch.setattr(doctor.subprocess, "run",
                        _fake_run({"projects": [{"name": "work", "local_path": str(vault)}]}))
    rc, msg = doctor.run()
    assert rc == 0 and "Tudo pronto" in msg


def test_cli_doctor_exit_code(vault, monkeypatch):
    from brainlib import cli
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    assert cli.main(["doctor"]) == 1

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))

from hook_payload import paths_from_patch, target_paths  # noqa: E402

PATCH = """*** Begin Patch
*** Update File: wiki/journal/Sessao 2026-08-13 x.md
@@
-a
+b
*** Add File: wiki/domains/infra/Nova Pagina.md
+conteudo
*** Delete File: wiki/domains/infra/Velha.md
*** End Patch
"""


def test_claude_shape_single_file():
    ev = {"cwd": "/repo", "tool_input": {"file_path": "/vault/wiki/journal/x.md"}}
    assert [p.as_posix() for p in target_paths(ev)] == ["/vault/wiki/journal/x.md"]


def test_codex_apply_patch_yields_every_touched_path():
    """Codex sends the patch text in tool_input.command and no file_path at
    all; without parsing it the validator sees nothing and waves the write
    through."""
    ev = {"cwd": "/vault", "tool_input": {"command": PATCH}}
    got = [p.as_posix() for p in target_paths(ev)]
    assert got == [
        "/vault/wiki/journal/Sessao 2026-08-13 x.md",
        "/vault/wiki/domains/infra/Nova Pagina.md",
        "/vault/wiki/domains/infra/Velha.md",
    ]


def test_move_destination_is_included():
    patch = "*** Begin Patch\n*** Update File: wiki/a.md\n*** Move to: wiki/b.md\n*** End Patch\n"
    got = [p.as_posix() for p in target_paths({"cwd": "/v", "tool_input": {"command": patch}})]
    assert got == ["/v/wiki/a.md", "/v/wiki/b.md"]


def test_absolute_paths_in_patch_are_not_rebased():
    patch = "*** Begin Patch\n*** Update File: /abs/wiki/a.md\n*** End Patch\n"
    assert [p.as_posix() for p in target_paths({"cwd": "/v", "tool_input": {"command": patch}})] == ["/abs/wiki/a.md"]


def test_plain_bash_command_is_not_a_patch():
    ev = {"cwd": "/v", "tool_input": {"command": "git status && echo '*** not a patch'"}}
    assert target_paths(ev) == []


def test_duplicates_collapse():
    patch = "*** Begin Patch\n*** Update File: wiki/a.md\n*** Update File: wiki/a.md\n*** End Patch\n"
    assert len(target_paths({"cwd": "/v", "tool_input": {"command": patch}})) == 1


def test_empty_payload_is_harmless():
    assert target_paths({}) == []
    assert paths_from_patch("") == []

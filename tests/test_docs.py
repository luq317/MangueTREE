"""Documentation required by the journal: files, sections, runnable example."""
import contextlib
import io
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EM_DASH = "—"

REQUIRED = ["README.md", "CITATION.cff", "CHANGELOG.md", "CONTRIBUTING.md",
            "docs/user-guide.md", "docs/methods.md", "docs/data-format.md",
            "docs/installers.md"]
REMOVED = ["DOCUMENTACAO.md", "ROADMAP.md", "INSTALADORES.md"]


def _md_files():
    return [p for p in ROOT.rglob("*.md")
            if not any(part in (".git", "build", "dist", ".venv")
                       or part.endswith(".egg-info") for part in p.relative_to(ROOT).parts)]


def test_required_docs_exist():
    for rel in REQUIRED:
        assert (ROOT / rel).is_file(), rel
    for rel in REMOVED:
        assert not (ROOT / rel).exists(), rel


def test_readme_sections():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    headings = {m.group(2).strip() for m in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.M)}
    for h in ("Installation", "Quick start", "Input data", "Validation", "Methods",
              "How to cite", "License"):
        assert h in headings, h
    assert "docs/images/screenshot.png" in text


def test_readme_library_example_runs(monkeypatch):
    monkeypatch.chdir(ROOT)
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"<!-- readme-example -->\s*```python\n(.*?)```", text, re.S)
    assert m, "marked example block not found"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(m.group(1), "README.md", "exec"), {"__name__": "__readme__"})
    printed = out.getvalue()
    assert "2977.8" in printed
    assert "26.55" in printed


def test_no_broken_links_to_removed_docs():
    for p in _md_files():
        text = p.read_text(encoding="utf-8")
        for old in REMOVED:
            assert old not in text, (p.name, old)


def test_citation_cff_fields():
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(r"^cff-version: 1\.2\.0$", text, re.M)
    assert re.search(r"^version: 1\.0\.0$", text, re.M)
    assert re.search(r"^license: MIT$", text, re.M)
    for name in ("Pereira", "Matta", "Chaves", "Soares"):
        assert f"family-names: {name}" in text or f'family-names: "{name}"' in text, name
    assert "0000-0002-1891-7621" in text


def test_no_em_dash_in_docs():
    files = _md_files() + [ROOT / "CITATION.cff"]
    for p in files:
        assert EM_DASH not in p.read_text(encoding="utf-8"), str(p)

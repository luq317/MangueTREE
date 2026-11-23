"""Repository hygiene checks required for the public release."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    return [f for f in out.splitlines() if (ROOT / f).exists()]


def test_required_files_exist():
    for rel in ("README.md", "LICENSE.txt", "pyproject.toml",
                "src/manguetree/__init__.py"):
        assert (ROOT / rel).is_file(), rel


def test_requirements_are_pinned():
    lines = [ln.strip() for ln in
             (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    assert lines
    for ln in lines:
        if ln == ".":        # installs the package itself (Streamlit Community Cloud)
            continue
        assert "==" in ln, ln


def test_no_deprecated_streamlit_args():
    for rel in _tracked_files():
        if rel.endswith(".py") and rel != "tests/test_repo.py":
            text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
            assert "use_container_width" not in text, rel


def test_no_private_lab_files():
    for rel in _tracked_files():
        for bad in ("Ilha", "dados_demostracao", "T2 - "):
            assert bad not in rel, rel


def test_license_is_gpl3_with_authors():
    text = (ROOT / "LICENSE.txt").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in text
    assert "Version 3, 29 June 2007" in text
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ("Copyright (c) 2026 Lucas Silva Pereira, Laiza Lacerda Motta, "
            "Tatiane Costa da Matta, Filipe de Oliveira Chaves, "
            "Mário Luiz Gomes Soares") in readme
    assert 'license = "GPL-3.0-or-later"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_source_files_carry_license_notice():
    for path in (ROOT / "src" / "manguetree").rglob("*.py"):
        assert "GNU General Public License" in path.read_text(encoding="utf-8")[:900], path


def test_branding_has_no_linkedin_or_title():
    from manguetree import branding
    assert branding.EMAIL == "pereira.lucas_1@posgraduacao.uerj.br"
    assert not hasattr(branding, "LINKEDIN")
    assert not hasattr(branding, "AUTOR_TITULO")
    assert not hasattr(branding, "rodape_texto")     # no personal footer lines


def test_no_wrong_github_user_link():
    import re
    pat = re.compile(r"github\.com/luq31(?!7)")
    for rel in _tracked_files():
        if rel.endswith((".py", ".md")) and rel != "tests/test_repo.py":
            text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
            assert not pat.search(text), rel

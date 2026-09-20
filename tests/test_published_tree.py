"""Integrity checks for the published data.

Readers reach these figures by clicking through markdown, so a link that does
not resolve is the failure that matters here: nothing else in the repository
would notice, and the pages are written by a generator from a list of subtypes
rather than from the files on disk.

Run from the repository root:

    pytest

Nothing here needs the analysis code. These tests read what is published.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# one directory per paper, named <first author>-<year>-<identifier>, where the
# identifier is the PMID when there is one and something readable when there is
# not -- a book chapter has no PMID.
PAPERS = sorted(d for d in ROOT.iterdir()
                if d.is_dir() and re.match(r"^[a-z]+-\d{4}-", d.name))

MARKDOWN = sorted(p for p in ROOT.rglob("*.md") if ".git" not in p.parts)

# <img src="..."> and [text](target)
REF = re.compile(r'<img\s+[^>]*src="([^"]+)"|\[[^\]]*\]\(([^)]+)\)')


def _targets(md):
    for m in REF.finditer(md.read_text(errors="replace")):
        target = m.group(1) or m.group(2)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        yield target.split("#", 1)[0]


def _unresolved(md):
    return sorted({t for t in _targets(md) if t and not (md.parent / t).exists()})


# --------------------------------------------------------------- structure

def test_there_are_papers_to_check():
    assert PAPERS, "no paper directories found; has the layout changed?"


@pytest.mark.parametrize("paper", PAPERS, ids=lambda p: p.name)
def test_every_paper_has_a_front_page(paper):
    assert (paper / "README.md").is_file(), f"{paper.name} has no README.md"


@pytest.mark.parametrize("paper", PAPERS, ids=lambda p: p.name)
def test_the_root_page_links_to_every_paper(paper):
    root = (ROOT / "README.md").read_text()
    assert paper.name in root, f"the root README does not mention {paper.name}"


@pytest.mark.parametrize("paper", PAPERS, ids=lambda p: p.name)
def test_the_front_page_carries_a_citation(paper):
    text = (paper / "README.md").read_text()
    assert "## Citation" in text, f"{paper.name}/README.md has no Citation section"
    assert "doi.org/" in text, f"{paper.name}/README.md cites no DOI"


@pytest.mark.parametrize("paper", PAPERS, ids=lambda p: p.name)
def test_the_directory_name_matches_the_identifier_it_cites(paper):
    """lee-2023-pmid-37540602 must be the paper whose PMID is 37540602."""
    parts = paper.name.split("-", 3)
    if len(parts) < 4 or parts[2] != "pmid":
        pytest.skip(f"{paper.name} is not keyed on a PMID")
    text = (paper / "README.md").read_text()
    assert parts[3] in text, f"{paper.name} does not cite PMID {parts[3]}"


# ------------------------------------------------------------------ links

@pytest.mark.parametrize("md", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_dead_links(md):
    assert _unresolved(md) == [], f"{md.relative_to(ROOT)} points at missing files"


def test_a_directory_a_front_page_links_to_opens_on_an_index():
    """A link to a directory must land on a page, not a file listing.

    Most directories here are reached through a named page -- the aminergic tree
    uses `acc_subfamily_heatmap.md` throughout -- and that is fine. What matters
    is that a front page never points a reader at a bare directory.
    """
    missing = []
    for paper in PAPERS:
        readme = paper / "README.md"
        for m in REF.finditer(readme.read_text()):
            target = (m.group(1) or m.group(2) or "").split("#", 1)[0]
            if not target or target.startswith(("http", "#", "mailto:")):
                continue
            dest = (readme.parent / target)
            if dest.is_dir() and not any((dest / n).is_file()
                                         for n in ("readme.md", "README.md")):
                missing.append(str(dest.relative_to(ROOT)))
    assert missing == [], f"front pages link to directories with no index: {missing}"


# ----------------------------------------------------------------- hygiene

def test_gitignore_hides_nothing_that_is_tracked():
    """A rule that matches published data reads as a mass deletion.

    This repository's content is data files, so extension-shaped rules are
    dangerous: `*.tar.gz` would have hidden the seven published MD trajectory
    archives, and `*_notext.png` the 948 label-free figures the aminergic tree
    ships. Both looked like housekeeping.
    """
    import subprocess
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "HEAD"],
                             capture_output=True, text=True).stdout
    if not tracked.strip():
        pytest.skip("no git history to check against")
    hidden = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--stdin"],
                            input=tracked, capture_output=True, text=True).stdout.split()
    assert hidden == [], f"{len(hidden)} tracked files would be ignored, e.g. {hidden[:3]}"


def test_no_operating_system_litter():
    junk = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
            if p.name in (".DS_Store", "Thumbs.db", "desktop.ini")
            and ".git" not in p.parts]
    assert junk == [], f"remove these and check .gitignore covers them: {junk}"


def test_no_empty_directories():
    empty = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
             if p.is_dir() and ".git" not in p.parts and not any(p.iterdir())]
    assert empty == [], f"empty directories: {empty}"

"""Unit tests for bishop_shared.rubric_assets (prompt-caching plan T1 / T2)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import tiktoken

from bishop_shared.profile_renderer import load_profile, render_profile_prompt
from bishop_shared.rubric_assets import (
    PROMPTS_CONTAINER_DIR,
    RubricDocument,
    compute_rubric_hash,
    load_rubric,
    resolve_rubric_path,
    verify_rubric_hash,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_BODY = "# Rubric\n\nSome guidance text.\nSecond line.\n"


def _make_asset(
    tmp_path: Path, *, rubric_id: str, version: str, body: str, digest: str, name: str | None = None
) -> Path:
    path = tmp_path / f"{name or rubric_id}.md"
    path.write_text(
        f'---\nrubric_id: {rubric_id}\nversion: "{version}"\ncanonical_hash: "{digest}"\n---\n{body}',
        encoding="utf-8",
        newline="\n",
    )
    return path


def test_resolve_rubric_path_all_three_ids() -> None:
    assert resolve_rubric_path("prefilter_rubric") == PROMPTS_CONTAINER_DIR / "prefilter_rubric_v1.md"
    assert resolve_rubric_path("call1_rubric") == PROMPTS_CONTAINER_DIR / "call1_rubric_v1.md"
    assert resolve_rubric_path("call2_rubric") == PROMPTS_CONTAINER_DIR / "call2_rubric_v1.md"


def test_resolve_rubric_path_unknown_id_raises() -> None:
    with pytest.raises(ValueError, match="Unknown rubric_id"):
        resolve_rubric_path("not_a_real_rubric")  # type: ignore[arg-type]


def test_front_matter_parse(tmp_path: Path) -> None:
    digest = compute_rubric_hash(_BODY)
    path = _make_asset(tmp_path, rubric_id="prefilter_rubric", version="1.0.0", body=_BODY, digest=digest)
    doc = load_rubric(path)
    assert doc == RubricDocument(
        rubric_id="prefilter_rubric", version="1.0.0", canonical_hash=digest, body=_BODY
    )


def test_stamp_and_verify_round_trip(tmp_path: Path) -> None:
    correct_digest = compute_rubric_hash(_BODY)
    path = _make_asset(
        tmp_path, rubric_id="call1_rubric", version="1.0.0", body=_BODY, digest="0" * 64
    )
    assert verify_rubric_hash("call1_rubric", rubric_path=path) is None

    # scripts/rubric_hash.py stamps the recomputed hash in place.
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "rubric_hash.py"), str(path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    assert "stamped canonical_hash" in result.stdout
    assert correct_digest in path.read_text(encoding="utf-8")

    verified = verify_rubric_hash("call1_rubric", rubric_path=path)
    assert verified == ("call1_rubric", "1.0.0", correct_digest)


def test_verify_rubric_hash_mismatch_returns_none(tmp_path: Path) -> None:
    path = _make_asset(
        tmp_path, rubric_id="call2_rubric", version="1.0.0", body=_BODY, digest="deadbeef" * 8
    )
    assert verify_rubric_hash("call2_rubric", rubric_path=path) is None


def test_verify_rubric_hash_unknown_rubric_id_raises_without_explicit_path() -> None:
    with pytest.raises(ValueError, match="Unknown rubric_id"):
        verify_rubric_hash("not_a_real_rubric")  # type: ignore[arg-type]


def test_crlf_and_lf_body_yield_same_hash() -> None:
    lf_body = "line one\nline two\nline three\n"
    crlf_body = lf_body.replace("\n", "\r\n")
    assert compute_rubric_hash(lf_body) == compute_rubric_hash(crlf_body)


def test_crlf_asset_on_disk_hashes_same_as_lf_asset(tmp_path: Path) -> None:
    lf_body = "alpha\nbeta\ngamma\n"
    digest = compute_rubric_hash(lf_body)
    lf_path = _make_asset(tmp_path, rubric_id="prefilter_rubric", version="1.0.0", body=lf_body, digest=digest)

    crlf_path = tmp_path / "crlf_variant.md"
    crlf_path.write_bytes(lf_path.read_bytes().replace(b"\n", b"\r\n"))

    assert compute_rubric_hash(lf_path) == compute_rubric_hash(crlf_path)


def test_version_edit_does_not_change_hash(tmp_path: Path) -> None:
    digest = compute_rubric_hash(_BODY)
    path_v1 = _make_asset(
        tmp_path, rubric_id="prefilter_rubric", version="1.0.0", body=_BODY, digest=digest, name="v1"
    )
    path_v2 = _make_asset(
        tmp_path, rubric_id="prefilter_rubric", version="2.0.0", body=_BODY, digest=digest, name="v2"
    )
    assert compute_rubric_hash(path_v1) == compute_rubric_hash(path_v2) == digest


def test_one_character_body_edit_changes_hash() -> None:
    original = compute_rubric_hash(_BODY)
    tampered = compute_rubric_hash(_BODY + "x")
    assert original != tampered


def test_call1_rubric_v1_asset_exists_and_verifies() -> None:
    """T3 (prompt-caching, cache key B): the real, committed
    ``config/prompts/call1_rubric_v1.md`` asset must exist on disk, parse as
    a well-formed rubric document, and its stamped ``canonical_hash`` must
    match a fresh recompute of its body. The generic round-trip tests above
    only exercise synthetic ``tmp_path`` fixtures — they cannot catch a
    stamping mistake, a line-ending drift, or a malformed front-matter edit
    in the actual authored file T3 ships, which is exactly the failure mode
    that would silently abort Call 1's rubric-verify-or-abort gate (§2 row
    12) in production."""
    path = REPO_ROOT / "config" / "prompts" / "call1_rubric_v1.md"
    assert path.is_file()

    doc = load_rubric(path)
    assert doc.rubric_id == "call1_rubric"

    verified = verify_rubric_hash("call1_rubric", rubric_path=path)
    assert verified is not None
    rubric_id, version, canonical_hash = verified
    assert rubric_id == "call1_rubric"
    assert version == doc.version
    assert canonical_hash == doc.canonical_hash


def test_rubric_hash_cli_exits_nonzero_when_canonical_hash_line_missing(tmp_path: Path) -> None:
    """T1-bis adversarial micro-pass falsifier (§2.1): scripts/rubric_hash.py's
    stamping path assumes exactly one `canonical_hash:` line exists to rewrite
    (`re.subn(..., count=1)` then `if count != 1: raise SystemExit(...)`). An
    asset missing that front-matter field entirely — a real authoring mistake,
    not a synthetic shape — must fail loudly (nonzero exit, no silent no-op
    write) instead of stamping nothing and reporting success."""
    path = tmp_path / "malformed.md"
    path.write_text(
        '---\nrubric_id: prefilter_rubric\nversion: "1.0.0"\n---\n# Rubric\nbody text\n',
        encoding="utf-8",
        newline="\n",
    )
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "rubric_hash.py"), str(path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "could not locate canonical_hash line" in (result.stdout + result.stderr)


# --- T2: config/prompts/prefilter_rubric_v1.md (pre-filter source-shape annex) ---

_PREFILTER_RUBRIC_PATH = REPO_ROOT / "config" / "prompts" / "prefilter_rubric_v1.md"

# The seven adapters actually registered in
# services/scraper/app/adapters/registry.py::ADAPTER_REGISTRY, mirrored here as
# source-name literals rather than importing bishop_shared.enums.SourceEnum, so
# this rubric-content test tracks the registration list the packet's kill
# criterion is anchored to ("the M8 adapter set") without adding a coupling to
# a shared import surface another subtask edits independently.
_M8_ADAPTER_SOURCE_NAMES = frozenset(
    {
        "arxiv",
        "github",
        "huggingface",
        "lesswrong",
        "openreview",
        "paperswithcode",
        "semantic_scholar",
    }
)


def test_prefilter_rubric_v1_resolves_and_hash_verifies() -> None:
    """The committed asset resolves via the real container-path mapping (not a
    tmp_path stand-in) and its stamped canonical_hash matches its own body."""
    assert resolve_rubric_path("prefilter_rubric") == PROMPTS_CONTAINER_DIR / "prefilter_rubric_v1.md"
    verified = verify_rubric_hash("prefilter_rubric", rubric_path=_PREFILTER_RUBRIC_PATH)
    assert verified is not None
    rubric_id, version, canonical_hash = verified
    assert rubric_id == "prefilter_rubric"
    assert version == "1.0.0"
    assert canonical_hash == compute_rubric_hash(_PREFILTER_RUBRIC_PATH)


def test_prefilter_rubric_v1_front_matter_matches_shared_schema() -> None:
    """§2 row 7 literal schema, shared verbatim with T3/T4: the on-disk file's
    front matter matches the exact block shape, not just a parseable subset."""
    raw = _PREFILTER_RUBRIC_PATH.read_text(encoding="utf-8")
    assert re.match(
        r'\A---\nrubric_id: prefilter_rubric\nversion: "[^"\n]+"\n'
        r'canonical_hash: "[0-9a-f]{64}"\n---\n',
        raw,
    ), "front matter does not match the shared rubric schema"


def test_prefilter_rubric_v1_clears_key_a_token_floor() -> None:
    """§2 row 8: measured against the real prefilter profile render (the pin
    key A actually uses at cache-time — professional_v1.2.0_soft_launch.yaml,
    not the enrichment pin), the total prefix (profile render + annex body)
    clears the 4,506-token floor with positive margin. This is the packet's
    own kill-criterion falsifier for "sizes its annex to meet the floor" — a
    padding-free content-sizing claim, not a mechanical afterthought. T10
    re-verifies the same floor at closure across all three keys; this test is
    T2's own proof for key A, in T2's own diff."""
    encoding = tiktoken.get_encoding("cl100k_base")
    profile = load_profile(Path("config/profiles/professional_v1.2.0_soft_launch.yaml"))
    profile_prompt = render_profile_prompt(profile)
    profile_tokens = len(encoding.encode(profile_prompt))

    rubric_doc = load_rubric(_PREFILTER_RUBRIC_PATH)
    annex_tokens = len(encoding.encode(rubric_doc.body))

    total = profile_tokens + annex_tokens
    assert total >= 4506, (
        f"key A total prefix {total} tokens (profile={profile_tokens}, "
        f"annex={annex_tokens}) is below the 4,506-token floor"
    )


def test_prefilter_rubric_v1_names_only_m8_registered_adapters() -> None:
    """Kill criterion: 'HALT if the annex names a specific source not in the
    M8 adapter set.' Extracts every source-name token from the annex's five
    '## Shape N — <shape> (<sources>)' headers and asserts each one is among
    the seven adapters actually registered in
    services/scraper/app/adapters/registry.py::ADAPTER_REGISTRY.

    Mutation-checked: inserting a fictitious source name into a shape header
    (e.g. appending ", reddit" to the Shape 1 parenthetical) makes this
    assertion fail; reverting restores green (verified by hand while
    authoring, then reverted — see decision log). This only proves the named
    set is a *subset* of the registered adapters, not that it is exhaustive
    — a real registered adapter omitted from every header is a gap this test
    cannot see."""
    body = load_rubric(_PREFILTER_RUBRIC_PATH).body
    headers = re.findall(r"^## Shape \d+ — [\w\s]+\(([^)]+)\)", body, re.MULTILINE)
    assert headers, "no '## Shape N — <name> (<sources>)' headers found in the annex"
    named_sources = {token.strip() for group in headers for token in group.split(",")}
    assert named_sources, "no source names extracted from shape headers"
    unregistered = named_sources - _M8_ADAPTER_SOURCE_NAMES
    assert not unregistered, f"annex names sources outside the M8 adapter set: {unregistered}"

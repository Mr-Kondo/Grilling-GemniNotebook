#!/usr/bin/env python3
"""Read-only Gemini Notebook (NotebookLM) authentication & source client for grilling-gemini-notebook.

Provides deterministic preflight authentication verification, headless session
refresh (`nlm auth refresh`), notebook URL/name resolution, source listing, and
raw source fulltext retrieval via `nlm` (`notebooklm-mcp-cli`), with explicit
local-directory fallback when requested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

NOTEBOOK_URL_RE = re.compile(r"/notebook/([A-Za-z0-9_-]+)")
UUID_LIKE_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
READABLE_EXTS = {".md", ".txt", ".ipynb", ".json", ".csv"}


def find_nlm() -> str | None:
    """Locate the `nlm` executable on PATH or standard uv/local bin locations."""
    found = shutil.which("nlm")
    if found:
        return found
    for candidate in (
        Path.home() / ".local" / "bin" / "nlm",
        Path("/opt/homebrew/bin/nlm"),
        Path("/usr/local/bin/nlm"),
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def run_nlm(args: list[str], profile: str | None = None, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    """Run a read-only `nlm` command and capture stdout/stderr."""
    nlm_bin = find_nlm()
    if not nlm_bin:
        raise FileNotFoundError("nlm executable not found. Install via: uv tool install notebooklm-mcp-cli")
    cmd = [nlm_bin, *args]
    if profile:
        cmd.extend(["--profile", profile])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def extract_notebook_id_from_url(notebook_ref: str) -> str | None:
    """Extract notebook ID if `notebook_ref` is a NotebookLM URL."""
    match = NOTEBOOK_URL_RE.search(notebook_ref.strip())
    if match:
        return match.group(1)
    return None


def check_auth(profile: str | None = None, auto_refresh: bool = True) -> dict[str, Any]:
    """Check `nlm login --check` and optionally attempt headless `nlm auth refresh`."""
    nlm_bin = find_nlm()
    if not nlm_bin:
        return {
            "status": "NLM_NOT_INSTALLED",
            "authenticated": False,
            "nlm_path": None,
            "profile": profile or "default",
            "auto_refresh_attempted": False,
            "message": "nlm CLI is not installed.",
            "remediation": "uv tool install notebooklm-mcp-cli && nlm login --storage protected",
        }

    proc = run_nlm(["login", "--check"], profile=profile)
    if proc.returncode == 0:
        return {
            "status": "AUTHENTICATED",
            "authenticated": True,
            "nlm_path": nlm_bin,
            "profile": profile or "default",
            "auto_refresh_attempted": False,
            "message": (proc.stdout or "Authentication valid.").strip(),
            "remediation": None,
        }

    refresh_attempted = False
    refresh_output = ""
    if auto_refresh:
        refresh_attempted = True
        ref_proc = run_nlm(["auth", "refresh"], profile=profile, timeout=60)
        refresh_output = (ref_proc.stdout + "\n" + ref_proc.stderr).strip()
        if ref_proc.returncode == 0:
            recheck = run_nlm(["login", "--check"], profile=profile)
            if recheck.returncode == 0:
                return {
                    "status": "AUTHENTICATED",
                    "authenticated": True,
                    "nlm_path": nlm_bin,
                    "profile": profile or "default",
                    "auto_refresh_attempted": True,
                    "message": (recheck.stdout or "Authentication refreshed headlessly.").strip(),
                    "remediation": None,
                }

    err_msg = (proc.stdout + "\n" + proc.stderr).strip()
    if refresh_output:
        err_msg = f"{err_msg}\n[auto-refresh]: {refresh_output}".strip()

    return {
        "status": "AUTH_REQUIRED",
        "authenticated": False,
        "nlm_path": nlm_bin,
        "profile": profile or "default",
        "auto_refresh_attempted": refresh_attempted,
        "message": err_msg or "Not authenticated with Gemini Notebook (NotebookLM).",
        "remediation": "nlm login --storage protected",
    }


def resolve_notebook(notebook_ref: str, profile: str | None = None) -> dict[str, Any]:
    """Resolve a NotebookLM URL, ID, or title into `{id, title, resolution_mode}`."""
    url_id = extract_notebook_id_from_url(notebook_ref)
    if url_id:
        title = url_id
        proc = run_nlm(["notebook", "list", "--json"], profile=profile)
        if proc.returncode == 0:
            try:
                notebooks = json.loads(proc.stdout)
                for nb in notebooks:
                    if str(nb.get("id")) == url_id:
                        title = nb.get("title") or url_id
                        break
            except json.JSONDecodeError:
                pass
        return {
            "input": notebook_ref,
            "id": url_id,
            "title": title,
            "resolution_mode": "url_extracted",
        }

    proc = run_nlm(["notebook", "list", "--json"], profile=profile)
    if proc.returncode != 0:
        if UUID_LIKE_RE.match(notebook_ref.strip()):
            return {
                "input": notebook_ref,
                "id": notebook_ref.strip(),
                "title": notebook_ref.strip(),
                "resolution_mode": "direct_uuid",
            }
        raise RuntimeError((proc.stderr or proc.stdout or "Failed to list notebooks").strip())

    notebooks = json.loads(proc.stdout or "[]")
    target = notebook_ref.strip()
    target_lower = target.lower()

    for nb in notebooks:
        if str(nb.get("id", "")) == target:
            return {
                "input": notebook_ref,
                "id": str(nb["id"]),
                "title": str(nb.get("title", target)),
                "resolution_mode": "exact_id",
            }

    for nb in notebooks:
        if str(nb.get("title", "")).strip().lower() == target_lower:
            return {
                "input": notebook_ref,
                "id": str(nb["id"]),
                "title": str(nb.get("title", target)),
                "resolution_mode": "exact_title",
            }

    for nb in notebooks:
        if target_lower in str(nb.get("title", "")).strip().lower():
            return {
                "input": notebook_ref,
                "id": str(nb["id"]),
                "title": str(nb.get("title", target)),
                "resolution_mode": "substring_title",
            }

    if UUID_LIKE_RE.match(target):
        return {
            "input": notebook_ref,
            "id": target,
            "title": target,
            "resolution_mode": "direct_uuid",
        }

    raise LookupError(f"Notebook not found for reference: {notebook_ref}")


def list_local_sources(local_dir: Path) -> list[dict[str, Any]]:
    """List readable local files as an explicit fallback when requested."""
    if not local_dir.exists() or not local_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(local_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in READABLE_EXTS:
            rel = str(path.relative_to(local_dir))
            items.append(
                {
                    "id": rel,
                    "title": path.name,
                    "type": "local_file",
                    "path": str(path.resolve()),
                }
            )
    return items


def cmd_list_sources(
    notebook_ref: str,
    profile: str | None = None,
    local_dir: Path | None = None,
    auto_refresh: bool = True,
) -> tuple[int, dict[str, Any]]:
    """List sources in a notebook via live `nlm` or explicit `--local-dir` fallback."""
    auth = check_auth(profile=profile, auto_refresh=auto_refresh)
    if auth["authenticated"]:
        try:
            nb = resolve_notebook(notebook_ref, profile=profile)
            proc = run_nlm(["source", "list", nb["id"], "--json"], profile=profile)
            if proc.returncode == 0:
                sources = json.loads(proc.stdout or "[]")
                return 0, {
                    "status": "OK",
                    "access_route": "nlm_live",
                    "read_only": True,
                    "notebook": nb,
                    "source_count": len(sources),
                    "sources": sources,
                }
            live_err = (proc.stderr or proc.stdout or "Failed to list sources via nlm").strip()
        except (RuntimeError, LookupError, json.JSONDecodeError, OSError, subprocess.SubprocessError) as exc:
            live_err = str(exc)
    else:
        live_err = auth["message"]

    if local_dir is not None:
        sources = list_local_sources(local_dir)
        return 0, {
            "status": "OK",
            "access_route": "local_fallback",
            "read_only": True,
            "live_error": live_err,
            "notebook": {"input": notebook_ref, "id": "local", "title": local_dir.name},
            "source_count": len(sources),
            "sources": sources,
        }

    code = 2 if not auth["authenticated"] else 1
    return code, {
        "status": auth["status"] if not auth["authenticated"] else "ERROR",
        "access_route": "none",
        "read_only": True,
        "notebook": {"input": notebook_ref},
        "message": live_err,
        "remediation": auth.get("remediation") or "Verify notebook URL/ID or pass --local-dir for local fallback.",
    }


def match_source(sources: list[dict[str, Any]], source_ref: str) -> dict[str, Any]:
    """Match a source entry by ID, exact title, or case-insensitive substring."""
    target = source_ref.strip()
    target_lower = target.lower()

    for src in sources:
        if str(src.get("id", "")) == target:
            return src
    for src in sources:
        if str(src.get("title", "")).strip().lower() == target_lower:
            return src
    for src in sources:
        if target_lower in str(src.get("title", "")).strip().lower() or target_lower in str(src.get("id", "")).lower():
            return src
    raise LookupError(f"Source '{source_ref}' not found among {len(sources)} source(s).")


def cmd_fetch_source(
    notebook_ref: str,
    source_ref: str,
    profile: str | None = None,
    local_dir: Path | None = None,
    auto_refresh: bool = True,
) -> tuple[int, dict[str, Any]]:
    """Fetch raw source fulltext (read-only) via live `nlm` or explicit `--local-dir` fallback."""
    code, list_payload = cmd_list_sources(
        notebook_ref=notebook_ref,
        profile=profile,
        local_dir=local_dir,
        auto_refresh=auto_refresh,
    )
    if code != 0:
        return code, list_payload

    sources = list_payload.get("sources", [])
    try:
        matched = match_source(sources, source_ref)
    except LookupError as exc:
        return 1, {
            "status": "SOURCE_NOT_FOUND",
            "access_route": list_payload["access_route"],
            "read_only": True,
            "notebook": list_payload["notebook"],
            "available_sources": [{"id": s.get("id"), "title": s.get("title")} for s in sources],
            "message": str(exc),
        }

    if list_payload["access_route"] == "nlm_live":
        src_id = str(matched["id"])
        proc = run_nlm(["source", "content", src_id, "--json"], profile=profile)
        if proc.returncode != 0:
            return 1, {
                "status": "ERROR",
                "access_route": "nlm_live",
                "read_only": True,
                "notebook": list_payload["notebook"],
                "source": matched,
                "message": (proc.stderr or proc.stdout or "Failed to fetch source content").strip(),
            }
        raw_item = json.loads(proc.stdout or "{}")
        content_text = str(raw_item.get("content", ""))
        sha256 = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
        return 0, {
            "status": "OK",
            "access_route": "nlm_live",
            "read_only": True,
            "data_boundary": "untrusted_readonly_source_text",
            "notebook": list_payload["notebook"],
            "source": {
                "input": source_ref,
                "id": src_id,
                "title": raw_item.get("title") or matched.get("title") or src_id,
                "type": matched.get("type", "unknown"),
            },
            "content_sha256": sha256,
            "content_length": len(content_text),
            "content": content_text,
        }

    local_path = Path(matched["path"])
    content_text = local_path.read_text(encoding="utf-8")
    sha256 = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
    return 0, {
        "status": "OK",
        "access_route": "local_fallback",
        "read_only": True,
        "data_boundary": "untrusted_readonly_source_text",
        "notebook": list_payload["notebook"],
        "source": {
            "input": source_ref,
            "id": matched["id"],
            "title": matched["title"],
            "path": str(local_path),
        },
        "content_sha256": sha256,
        "content_length": len(content_text),
        "content": content_text,
    }


def emit(payload: dict[str, Any], out_path: Path | None = None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Gemini Notebook (NotebookLM) auth & source helper"
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_status = sub.add_parser("status", help="Check NotebookLM authentication status")
    p_status.add_argument("--profile", default=None, help="nlm profile name")
    p_status.add_argument(
        "--no-auto-refresh",
        action="store_true",
        help="Disable automatic headless refresh (`nlm auth refresh`) when check fails",
    )
    p_status.add_argument("--out", type=Path, default=None, help="Optional JSON output file path")

    p_resolve = sub.add_parser("resolve", help="Resolve a NotebookLM URL, ID, or title")
    p_resolve.add_argument("--notebook", required=True, help="Notebook URL, ID, or title")
    p_resolve.add_argument("--profile", default=None, help="nlm profile name")
    p_resolve.add_argument("--out", type=Path, default=None, help="Optional JSON output file path")

    p_list = sub.add_parser("list-sources", help="List sources in a notebook")
    p_list.add_argument("--notebook", required=True, help="Notebook URL, ID, or title")
    p_list.add_argument("--profile", default=None, help="nlm profile name")
    p_list.add_argument("--local-dir", type=Path, default=None, help="Optional local fallback directory")
    p_list.add_argument("--no-auto-refresh", action="store_true", help="Disable automatic headless refresh")
    p_list.add_argument("--out", type=Path, default=None, help="Optional JSON output file path")

    p_fetch = sub.add_parser("fetch-source", help="Fetch raw source content (read-only)")
    p_fetch.add_argument("--notebook", required=True, help="Notebook URL, ID, or title")
    p_fetch.add_argument("--source", required=True, help="Source title or ID")
    p_fetch.add_argument("--profile", default=None, help="nlm profile name")
    p_fetch.add_argument("--local-dir", type=Path, default=None, help="Optional local fallback directory")
    p_fetch.add_argument("--no-auto-refresh", action="store_true", help="Disable automatic headless refresh")
    p_fetch.add_argument("--out", type=Path, default=None, help="Optional JSON output file path")

    args = parser.parse_args()

    if args.subcommand == "status":
        res = check_auth(profile=args.profile, auto_refresh=not args.no_auto_refresh)
        emit(res, args.out)
        return 0 if res["authenticated"] else 2

    if args.subcommand == "resolve":
        url_id = extract_notebook_id_from_url(args.notebook)
        auth = check_auth(profile=args.profile, auto_refresh=True)
        if not auth["authenticated"] and url_id:
            emit(
                {
                    "status": "OK_OFFLINE_URL",
                    "authenticated": False,
                    "notebook": {
                        "input": args.notebook,
                        "id": url_id,
                        "title": url_id,
                        "resolution_mode": "url_extracted",
                    },
                },
                args.out,
            )
            return 0
        if not auth["authenticated"]:
            emit(auth, args.out)
            return 2
        try:
            nb = resolve_notebook(args.notebook, profile=args.profile)
            emit({"status": "OK", "authenticated": True, "notebook": nb}, args.out)
            return 0
        except (RuntimeError, LookupError, json.JSONDecodeError, OSError, subprocess.SubprocessError) as exc:
            emit({"status": "ERROR", "message": str(exc)}, args.out)
            return 1

    if args.subcommand == "list-sources":
        code, payload = cmd_list_sources(
            notebook_ref=args.notebook,
            profile=args.profile,
            local_dir=args.local_dir,
            auto_refresh=not args.no_auto_refresh,
        )
        emit(payload, args.out)
        return code

    if args.subcommand == "fetch-source":
        code, payload = cmd_fetch_source(
            notebook_ref=args.notebook,
            source_ref=args.source,
            profile=args.profile,
            local_dir=args.local_dir,
            auto_refresh=not args.no_auto_refresh,
        )
        emit(payload, args.out)
        return code

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

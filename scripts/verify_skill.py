#!/usr/bin/env python3
"""Verifier and environment reporter for grilling-gemini-notebook."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

SKILL_NAME = "grilling-gemini-notebook"
ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
CLIENT_SCRIPT = ROOT / "scripts" / "notebook_client.py"


def read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "0.0.0"


def print_env_record(model: str, app_name: str, app_version: str) -> int:
    payload = {
        "skill": SKILL_NAME,
        "version": read_version(),
        "os": f"{platform.system()} {platform.release()}",
        "app": {"name": app_name, "version": app_version},
        "model": model,
        "date": dt.date.today().isoformat(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(
        json.dumps({"save_to": f"~/.agents/skill-env/{SKILL_NAME}.json"}, ensure_ascii=False),
        file=sys.stderr,
    )
    return 0


def check_skill_files() -> list[str]:
    errors: list[str] = []
    skill_md = ROOT / "SKILL.md"
    nb_ref = ROOT / "references" / "notebook-access.md"
    rubric_ref = ROOT / "references" / "analogy-rubric.md"
    license_file = ROOT / "LICENSE"

    for p in (skill_md, nb_ref, rubric_ref, VERSION_FILE, CLIENT_SCRIPT, license_file):
        if not p.exists():
            errors.append(f"Missing required file: {p.relative_to(ROOT)}")
    if errors:
        return errors

    lic_text = license_file.read_text(encoding="utf-8")
    if "MIT License" not in lic_text or "Matt Pocock" not in lic_text:
        errors.append("LICENSE must contain MIT License and Matt Pocock attribution for grilling")

    text = skill_md.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not fm_match:
        errors.append("SKILL.md missing YAML frontmatter")
    else:
        fm = fm_match.group(1)
        if f"name: {SKILL_NAME}" not in fm:
            errors.append(f"SKILL.md frontmatter must have name: {SKILL_NAME}")
        if "license: MIT" not in fm:
            errors.append("SKILL.md frontmatter must have license: MIT")
        desc_match = re.search(r"description:\s*(.+)", fm)
        if not desc_match:
            errors.append("SKILL.md frontmatter missing description")
        else:
            desc = desc_match.group(1).strip().strip('"').strip("'")
            if not desc.startswith("Use when"):
                errors.append("SKILL.md description must start with 'Use when'")
            if len(desc) > 1024:
                errors.append(f"SKILL.md description exceeds 1024 chars ({len(desc)})")

    required_tokens = [
        "grilling",
        "references/notebook-access.md",
        "references/analogy-rubric.md",
        "scripts/notebook_client.py",
        "nlm auth refresh",
        "🎯 アナロジー適合度判定",
        "🔍 ファクトチェックと根拠・引用箇所",
        "Verified",
        "Partially Verified",
        "Refuted",
        "Unverified",
        "誠実",
        "GitHub Issue",
        "❓ **Q1**",
        "➡️",
    ]
    for token in required_tokens:
        if token not in text:
            errors.append(f"SKILL.md missing required contract token: {token}")

    nb_text = nb_ref.read_text(encoding="utf-8")
    for token in (
        "URL",
        "scripts/notebook_client.py",
        "nlm auth refresh",
        "nlm login --storage protected",
        "gemini-notebook-mcp",
        "/browser",
        "読み取り専用",
    ):
        if token not in nb_text:
            errors.append(f"references/notebook-access.md missing token: {token}")

    rubric_text = rubric_ref.read_text(encoding="utf-8")
    for token in ("Verified", "Unverified", "引用箇所", "GitHub Issue", "忖度"):
        if token not in rubric_text:
            errors.append(f"references/analogy-rubric.md missing token: {token}")

    proc = subprocess.run(
        [sys.executable, str(CLIENT_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        errors.append(f"scripts/notebook_client.py --help failed: {proc.stderr}")

    return errors


def check_live_auth() -> list[str]:
    errors: list[str] = []
    proc = subprocess.run(
        [sys.executable, str(CLIENT_SCRIPT), "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return [f"notebook_client.py status returned invalid JSON: {proc.stdout}"]

    if proc.returncode != 0 or not payload.get("authenticated"):
        errors.append(
            f"Live NotebookLM authentication is not active (status={payload.get('status')}). "
            f"Remediation: {payload.get('remediation')}"
        )
    return errors


def check_sample_output(sample_path: Path) -> list[str]:
    errors: list[str] = []
    if not sample_path.exists():
        return [f"Sample output file not found: {sample_path}"]
    text = sample_path.read_text(encoding="utf-8")
    required = [
        "🎯 アナロジー適合度判定",
        "対応マップ",
        "✅ 正確に合っている点",
        "⚠️ ズレている点・アナロジーの限界",
        "💡 より正確にするための補正案",
        "🔍 ファクトチェックと根拠・引用箇所",
        "引用箇所",
        "❓ **Q1**",
        "➡️",
    ]
    for token in required:
        if token not in text:
            errors.append(f"Sample output missing required section/token: {token}")
    if not any(s in text for s in ("Verified", "Partially Verified", "Refuted", "Unverified")):
        errors.append("Sample output missing fact-check verification status")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify grilling-gemini-notebook skill")
    parser.add_argument("--version", action="store_true", help="Print skill name and version")
    parser.add_argument("--env-record", action="store_true", help="Print read-only environment JSON")
    parser.add_argument("--model", default="unknown", help="Model name for --env-record")
    parser.add_argument("--app-name", default="antigravity-cli", help="Application name for --env-record")
    parser.add_argument("--app-version", default="unknown", help="Application version for --env-record")
    parser.add_argument("--check-output", type=Path, help="Verify a sample response markdown file")
    parser.add_argument(
        "--check-live-auth",
        action="store_true",
        help="Verify that live NotebookLM OAuth authentication (`nlm login --check` / `notebook_client.py status`) is active",
    )
    args = parser.parse_args()

    if args.version:
        print(f"{SKILL_NAME} {read_version()}")
        return 0
    if args.env_record:
        return print_env_record(args.model, args.app_name, args.app_version)

    errors = check_skill_files()
    if args.check_live_auth:
        errors.extend(check_live_auth())
    if args.check_output:
        errors.extend(check_sample_output(args.check_output))

    if errors:
        for err in errors:
            print(f"[FAIL] {err}", file=sys.stderr)
        return 1

    modes = ["skill structure"]
    if args.check_live_auth:
        modes.append("live NotebookLM auth")
    if args.check_output:
        modes.append("sample output")
    print(f"[PASS] {SKILL_NAME} v{read_version()} verified ({', '.join(modes)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

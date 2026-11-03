#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="grilling-gemini-notebook"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "${ROOT}/VERSION")"
TIMESTAMP="$(date +%Y%m%d%H%M%S)-$$"
BACKUP_ROOT="${HOME}/.local/state/${SKILL_NAME}/backups/${TIMESTAMP}"
MODE="${1:---install}"
case "${MODE}" in
  --install|--update|--uninstall|--verify|--version) ;;
  *) echo "Usage: $0 [--install|--update|--uninstall|--verify|--version]" >&2; exit 2 ;;
esac
if [[ "$#" -gt 1 ]]; then
  echo "Only one operation is supported" >&2
  exit 2
fi

TARGET_DIRS=(
  "${HOME}/.agents/skills/${SKILL_NAME}"
  "${HOME}/.gemini/antigravity-cli/skills/${SKILL_NAME}"
  "${HOME}/.gemini/config/skills/${SKILL_NAME}"
  "${HOME}/.claude/skills/${SKILL_NAME}"
  "${HOME}/.codex/skills/${SKILL_NAME}"
)

GRILLING_LINKS=(
  "${HOME}/.gemini/antigravity-cli/skills/grilling"
  "${HOME}/.gemini/config/skills/grilling"
  "${HOME}/.codex/skills/grilling"
)

SKILL_REL_FILES=(
  "SKILL.md"
  "VERSION"
  "LICENSE"
  "README.md"
  "references/notebook-access.md"
  "references/analogy-rubric.md"
  "scripts/notebook_client.py"
  "scripts/verify_skill.py"
  "scripts/install.sh"
)

if [[ "${MODE}" == "--version" ]]; then
  echo "${SKILL_NAME} ${VERSION}"
  exit 0
fi

verify_install() {
  local status=0
  for target in "${TARGET_DIRS[@]}"; do
    for rel in "${SKILL_REL_FILES[@]}"; do
      local src_file="${ROOT}/${rel}"
      local dst_file="${target}/${rel}"
      if [[ ! -f "${dst_file}" ]]; then
        echo "[FAIL] Missing installed file: ${dst_file}" >&2
        status=1
        continue
      fi
      local src_sha dst_sha
      src_sha="$(shasum -a 256 "${src_file}" | awk '{print $1}')"
      dst_sha="$(shasum -a 256 "${dst_file}" | awk '{print $1}')"
      if [[ "${src_sha}" != "${dst_sha}" ]]; then
        echo "[FAIL] Digest mismatch: ${dst_file}" >&2
        status=1
      fi
    done
  done
  if [[ -f "${HOME}/.agents/skills/grilling/SKILL.md" ]]; then
    for glink in "${GRILLING_LINKS[@]}"; do
      if [[ ! -f "${glink}/SKILL.md" ]]; then
        echo "[FAIL] Prerequisite grilling skill missing at: ${glink}" >&2
        status=1
      fi
    done
  fi
  if ! command -v nlm >/dev/null 2>&1 && [[ ! -x "${HOME}/.local/bin/nlm" ]]; then
    echo "[FAIL] nlm (notebooklm-mcp-cli) is not installed on this Mac" >&2
    status=1
  fi
  if [[ "${status}" -eq 0 ]]; then
    echo "[PASS] ${SKILL_NAME} v${VERSION} verified across all ${#TARGET_DIRS[@]} Mac agent directories (plus grilling prerequisite links & nlm CLI)."
  fi
  return "${status}"
}

if [[ "${MODE}" == "--verify" ]]; then
  verify_install
  exit $?
fi

# ADR: adr/2026-11-03-update-knowledge-layers.md. Never replace an unrelated skill.
for target in "${TARGET_DIRS[@]}"; do
  if [[ -e "${target}" || -L "${target}" ]]; then
    if [[ ! -f "${target}/SKILL.md" ]] || ! grep -Fxq "name: ${SKILL_NAME}" "${target}/SKILL.md"; then
      echo "[FAIL] Refusing to replace unrecognized skill: ${target}" >&2
      exit 1
    fi
  fi
done

backup_target() {
  local target="$1"
  local backup="${BACKUP_ROOT}/$(echo "${target}" | tr '/' '_')"
  mkdir -p "${BACKUP_ROOT}"
  mv "${target}" "${backup}"
  echo "[BACKUP] ${backup}"
}

if [[ "${MODE}" == "--uninstall" ]]; then
  for target in "${TARGET_DIRS[@]}"; do
    if [[ -e "${target}" || -L "${target}" ]]; then
      backup_target "${target}"
    fi
  done
  echo "[PASS] Skill removed; backups retained. grilling and nlm were not removed."
  exit 0
fi

python3 "${ROOT}/scripts/verify_skill.py"
for rel in "${SKILL_REL_FILES[@]}"; do
  [[ -f "${ROOT}/${rel}" ]] || { echo "[FAIL] Missing source: ${rel}" >&2; exit 1; }
done

STAGE=""
trap 'if [[ -n "${STAGE}" && -d "${STAGE}" ]]; then rm -rf "${STAGE}"; fi' EXIT

for target in "${TARGET_DIRS[@]}"; do
  mkdir -p "$(dirname "${target}")"
  STAGE="$(mktemp -d "${target}.stage.XXXXXX")"
  for rel in "${SKILL_REL_FILES[@]}"; do
    mkdir -p "$(dirname "${STAGE}/${rel}")"
    cp "${ROOT}/${rel}" "${STAGE}/${rel}"
  done
  chmod +x "${STAGE}/scripts/"*.py "${STAGE}/scripts/install.sh"
  backup="${BACKUP_ROOT}/$(echo "${target}" | tr '/' '_')"
  if [[ -e "${target}" || -L "${target}" ]]; then
    backup_target "${target}"
  fi
  if ! mv "${STAGE}" "${target}"; then
    if [[ -e "${backup}" || -L "${backup}" ]]; then
      mv "${backup}" "${target}"
    fi
    exit 1
  fi
  STAGE=""
done

if [[ -d "${HOME}/.agents/skills/grilling" ]]; then
  for glink in "${GRILLING_LINKS[@]}"; do
    if [[ ! -e "${glink}" ]]; then
      ln -s "${HOME}/.agents/skills/grilling" "${glink}"
    fi
  done
fi

verify_install

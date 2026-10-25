#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="grilling-gemini-notebook"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "${ROOT}/VERSION")"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
BACKUP_ROOT="${ROOT}/feedback/backups/${TIMESTAMP}"

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

if [[ "${1:-}" == "--version" ]]; then
  echo "${SKILL_NAME} ${VERSION}"
  exit 0
fi

verify_install() {
  local status=0
  for target in "${TARGET_DIRS[@]}"; do
    for rel in "SKILL.md" "VERSION" "references/notebook-access.md" "references/analogy-rubric.md" "scripts/verify_skill.py" "scripts/install.sh"; do
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
  if [[ "${status}" -eq 0 ]]; then
    echo "[PASS] ${SKILL_NAME} v${VERSION} verified across all ${#TARGET_DIRS[@]} Mac agent directories (plus grilling prerequisite links)."
  fi
  return "${status}"
}

if [[ "${1:-}" == "--verify" ]]; then
  verify_install
  exit $?
fi

python3 "${ROOT}/scripts/verify_skill.py"

for target in "${TARGET_DIRS[@]}"; do
  mkdir -p "$(dirname "${target}")"
  if [[ -e "${target}" || -L "${target}" ]]; then
    mkdir -p "${BACKUP_ROOT}"
    local_name="$(echo "${target}" | tr '/' '_')"
    cp -RL "${target}" "${BACKUP_ROOT}/${local_name}" 2>/dev/null || true
    rm -rf "${target}"
  fi
  mkdir -p "${target}/references" "${target}/scripts"
  cp "${ROOT}/SKILL.md" "${ROOT}/VERSION" "${ROOT}/README.md" "${target}/"
  cp "${ROOT}/references/notebook-access.md" "${ROOT}/references/analogy-rubric.md" "${target}/references/"
  cp "${ROOT}/scripts/verify_skill.py" "${ROOT}/scripts/install.sh" "${target}/scripts/"
  chmod +x "${target}/scripts/verify_skill.py" "${target}/scripts/install.sh"
done

if [[ -d "${HOME}/.agents/skills/grilling" ]]; then
  for glink in "${GRILLING_LINKS[@]}"; do
    if [[ ! -e "${glink}" ]]; then
      ln -s "${HOME}/.agents/skills/grilling" "${glink}"
    fi
  done
fi

verify_install

#!/usr/bin/env bash
#
# test-codex-skills.sh — verify Codex discovers the same source skills that
# Claude Code ships, without copying a second editable skill tree.
#
# The bridge must use symlinked directories because Codex supports them and a
# copied .agents/skills tree would drift from skills/ silently.

set -euo pipefail

INSTALLER_ONLY=0
case "$#" in
  0) ;;
  1) [ "$1" = "--installer-only" ] && INSTALLER_ONLY=1 || {
    echo "usage: bash scripts/test-codex-skills.sh [--installer-only]" >&2
    exit 2
  } ;;
  *) echo "usage: bash scripts/test-codex-skills.sh [--installer-only]" >&2; exit 2 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0
note() { printf '  %-8s %-22s %s\n' "$1" "$2" "${3:-}"; }

shopt -s nullglob
sources=(skills/*)
if [ "${#sources[@]}" -eq 0 ]; then
  note FAIL inventory "skills/ is empty"
  exit 1
fi

if [ "$INSTALLER_ONLY" -eq 0 ]; then
  if [ ! -d .agents/skills ]; then
    note FAIL bridge ".agents/skills is missing"
    exit 1
  fi

  for source in "${sources[@]}"; do
    name="${source#skills/}"
    target=".agents/skills/$name"

    if [ ! -f "$source/SKILL.md" ]; then
      note FAIL "$name" "source has no SKILL.md"
      fail=1
      continue
    fi

    if [ ! -L "$target" ]; then
      note FAIL "$name" "Codex bridge must be a symlink"
      fail=1
      continue
    fi

    if [ ! "$target/SKILL.md" -ef "$source/SKILL.md" ]; then
      note FAIL "$name" "bridge does not resolve to the source skill"
      fail=1
      continue
    fi

    note ok "$name" "shared source"
  done

  for target in .agents/skills/*; do
    name="${target#.agents/skills/}"
    if [ ! -d "skills/$name" ]; then
      note FAIL "$name" "Codex bridge has no source skill"
      fail=1
    fi
  done
else
  note SKIP bridge "installer-only mode"
fi

# Codex names manual skills with `$skill`. Keep Dovetail's two manual-only
# workflows explicit on that host without changing their Claude frontmatter.
manual_skills=(spark-steering upsum)
for name in "${manual_skills[@]}"; do
  policy="skills/$name/agents/openai.yaml"
  if [ ! -f "$policy" ]; then
    note FAIL "$name" "missing Codex invocation policy"
    fail=1
    continue
  fi
  implicit="$(awk '$1 == "allow_implicit_invocation:" { print $2; exit }' "$policy")"
  if [ "$implicit" != false ]; then
    note FAIL "$name" "must disable implicit Codex invocation"
    fail=1
    continue
  fi
  note ok "$name" "explicit-only in Codex"
done

# A global install must copy the source directories into the documented user
# location. It must not repoint the repository bridge or write to the real home.
if [ ! -f scripts/install-codex.sh ]; then
  note FAIL installer "scripts/install-codex.sh is missing"
  fail=1
else
  smoke_home="$(mktemp -d)"
  dry_home=""
  project_dir=""
  redirect_project=""
  redirected_destination=""
  skills_redirect_project=""
  skills_redirected_destination=""
  bridge_alias_project=""
  linkfile_fixture=""
  cleanup() {
    rm -rf "$smoke_home" "${dry_home:-}" "${project_dir:-}" \
      "${redirect_project:-}" "${redirected_destination:-}" \
      "${skills_redirect_project:-}" "${skills_redirected_destination:-}" \
      "${bridge_alias_project:-}" "${linkfile_fixture:-}"
  }
  trap cleanup EXIT

  if ! install_out="$(HOME="$smoke_home" bash scripts/install-codex.sh 2>&1)"; then
    note FAIL installer "global install failed"
    printf '%s\n' "$install_out" >&2
    fail=1
  else
    for source in "${sources[@]}"; do
      name="${source#skills/}"
      installed="$smoke_home/.agents/skills/$name"
      if [ ! -f "$installed/SKILL.md" ]; then
        note FAIL "$name" "installer omitted skill"
        fail=1
      elif [ -L "$installed" ]; then
        note FAIL "$name" "installer must copy, not link into the source checkout"
        fail=1
      elif ! cmp -s "$source/SKILL.md" "$installed/SKILL.md"; then
        note FAIL "$name" "installed SKILL.md differs from source"
        fail=1
      elif [ "$name" = spark-steering ] || [ "$name" = upsum ]; then
        if ! cmp -s "$source/agents/openai.yaml" "$installed/agents/openai.yaml"; then
          note FAIL "$name" "installer omitted Codex invocation policy"
          fail=1
        else
          note ok "$name" "installer copy"
        fi
      else
        note ok "$name" "installer copy"
      fi
    done
  fi

  # Existing copies are safe by default, but --force must repair a changed copy.
  if ! repeat_out="$(HOME="$smoke_home" bash scripts/install-codex.sh 2>&1)"; then
    note FAIL installer "second install failed"
    printf '%s\n' "$repeat_out" >&2
    fail=1
  elif ! printf '%s\n' "$repeat_out" | awk -v count="${#sources[@]}" '$0 == "0 installed, " count " skipped." { found=1 } END { exit !found }'; then
    note FAIL installer "existing copies were not all skipped"
    fail=1
  else
    note ok installer "existing copies skipped"
  fi

  tampered="$smoke_home/.agents/skills/prompt-engineering/SKILL.md"
  printf '\n<!-- installer smoke canary -->\n' >> "$tampered"
  if ! force_out="$(HOME="$smoke_home" bash scripts/install-codex.sh --force 2>&1)"; then
    note FAIL installer "forced replacement failed"
    printf '%s\n' "$force_out" >&2
    fail=1
  elif ! cmp -s skills/prompt-engineering/SKILL.md "$tampered"; then
    note FAIL installer "--force did not restore the source copy"
    fail=1
  else
    note ok installer "forced replacement restores source"
  fi

  dry_home="$(mktemp -d)"
  if ! dry_out="$(HOME="$dry_home" bash scripts/install-codex.sh --dry-run 2>&1)"; then
    note FAIL installer "dry run failed"
    printf '%s\n' "$dry_out" >&2
    fail=1
  elif [ -e "$dry_home/.agents" ]; then
    note FAIL installer "dry run wrote a destination"
    fail=1
  else
    note ok installer "dry run leaves no destination"
  fi

  project_dir="$(mktemp -d)"
  if ! project_out="$(cd "$project_dir" && bash "$ROOT/scripts/install-codex.sh" --project 2>&1)"; then
    note FAIL installer "project install failed"
    printf '%s\n' "$project_out" >&2
    fail=1
  else
    for source in "${sources[@]}"; do
      name="${source#skills/}"
      installed="$project_dir/.agents/skills/$name/SKILL.md"
      if ! cmp -s "$source/SKILL.md" "$installed"; then
        note FAIL "$name" "project installer copy differs from source"
        fail=1
      fi
    done
    [ "$fail" -eq 0 ] && note ok installer "project copy"
  fi

  # A project-controlled .agents link can redirect --project outside the
  # intended workspace. The installer must refuse before it creates a skill.
  redirect_project="$(mktemp -d)"
  redirected_destination="$(mktemp -d)"
  ln -s "$redirected_destination" "$redirect_project/.agents"
  if (cd "$redirect_project" && bash "$ROOT/scripts/install-codex.sh" --project >/dev/null 2>&1); then
    note FAIL installer "accepted a redirected project destination"
    fail=1
  elif [ -e "$redirected_destination/skills/prompt-engineering/SKILL.md" ]; then
    note FAIL installer "wrote through a redirected project destination"
    fail=1
  else
    note ok installer "redirected project destination refused"
  fi

  # A direct .agents/skills link is a separate traversal shape from a linked
  # parent directory and must be rejected before a copy or forced replacement.
  skills_redirect_project="$(mktemp -d)"
  skills_redirected_destination="$(mktemp -d)"
  mkdir -p "$skills_redirect_project/.agents"
  ln -s "$skills_redirected_destination" "$skills_redirect_project/.agents/skills"
  if (cd "$skills_redirect_project" && bash "$ROOT/scripts/install-codex.sh" --project >/dev/null 2>&1); then
    note FAIL installer "accepted a redirected project skills destination"
    fail=1
  elif [ -e "$skills_redirected_destination/prompt-engineering/SKILL.md" ]; then
    note FAIL installer "wrote through a redirected project skills destination"
    fail=1
  else
    note ok installer "redirected project skills destination refused"
  fi

  if [ "$INSTALLER_ONLY" -eq 0 ]; then
    # Alias the repository bridge from another project. Both normal and forced
    # installation must refuse without replacing the source symlinks with copies.
    bridge_alias_project="$(mktemp -d)"
    mkdir -p "$bridge_alias_project/.agents"
    ln -s "$ROOT/.agents/skills" "$bridge_alias_project/.agents/skills"
    bridge_before="$(readlink "$ROOT/.agents/skills/prompt-engineering")"
    if (cd "$bridge_alias_project" && bash "$ROOT/scripts/install-codex.sh" --project >/dev/null 2>&1) || \
       (cd "$bridge_alias_project" && bash "$ROOT/scripts/install-codex.sh" --project --force >/dev/null 2>&1); then
      note FAIL installer "accepted a project alias of the source bridge"
      fail=1
    elif [ ! -L "$ROOT/.agents/skills/prompt-engineering" ] || \
         [ "$(readlink "$ROOT/.agents/skills/prompt-engineering")" != "$bridge_before" ]; then
      note FAIL installer "project alias changed the source bridge"
      fail=1
    else
      note ok installer "source bridge alias refused"
    fi
  fi

  if bash scripts/install-codex.sh --project >/dev/null 2>&1; then
    note FAIL installer "must refuse a self-overwriting project install"
    fail=1
  else
    note ok installer "self-overwrite refused"
  fi

  # Windows Git can materialize tracked symlinks as ordinary text files. Exercise
  # that checkout shape on every installer-only run so this fallback never reads
  # or depends on the repository bridge.
  if [ "$INSTALLER_ONLY" -eq 1 ] && [ "${CODEX_LINKFILE_FIXTURE:-0}" -eq 0 ]; then
    linkfile_fixture="$(mktemp -d)"
    cp -a "$ROOT/." "$linkfile_fixture/repo"
    for bridge in "$linkfile_fixture/repo/.agents/skills/"*; do
      if [ -L "$bridge" ]; then
        target="$(readlink "$bridge")"
        rm "$bridge"
        printf '%s\n' "$target" > "$bridge"
      fi
    done
    if ! fixture_out="$(CODEX_LINKFILE_FIXTURE=1 bash "$linkfile_fixture/repo/scripts/test-codex-skills.sh" --installer-only 2>&1)"; then
      note FAIL installer "installer-only mode failed for a link-file checkout"
      printf '%s\n' "$fixture_out" >&2
      fail=1
    else
      note ok installer "installer-only supports a link-file checkout"
    fi
  fi
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "Codex bridge checks passed."
else
  echo "Codex bridge checks FAILED."
fi
exit "$fail"

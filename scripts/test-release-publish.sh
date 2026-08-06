#!/usr/bin/env bash
#
# test-release-publish.sh — prove the publish path checks before it writes, and
# that nothing else in this repository can write at all.
#
# `test-release-check.sh` asks whether the gate grades the commit it says it
# grades. This asks the question one layer out: given a gate that works, is
# there any route by which a tag gets made without it? The two failures are
# different -- a wrong verdict against a right one, versus a right verdict
# nobody waited for -- and they are checked apart because they fail apart.
#
# Two layers:
#
#   static     the shape of the workflows. That `release-publish.yml` cannot be
#              started by a tag; that the job holding `contents: write` runs
#              only after the job that does not; that the step which writes is
#              in that job and nowhere else; and that `release.yml`, which does
#              start from a tag, holds no write permission at all. That last one
#              is the mechanical form of a claim this repository now makes in
#              prose: a workflow triggered by a tag push audits, and cannot
#              publish. A comment saying so is a comment; a permissions block
#              saying so is enforced by GitHub.
#   behaviour  `publish-release.sh` against a throwaway repository, on every
#              input that should stop it -- and one that should not, so the
#              refusals are attributable to the input rather than to a script
#              that refuses everything.
#
# The behaviour layer's load-bearing assertion is the negative one: after a
# `--dry-run` that passed every check and reported the release publishable, no
# call that writes was made. That is asserted against a recorded log rather than
# against the absence of a tag, because a tag failing to appear is also what
# happens when the script dies early -- and a canary fires first, so an
# assertion that no write was logged cannot pass by way of a log nothing could
# ever have been written to.
#
# `gh` is stubbed throughout. The stub answers check 6 in the affirmative, which
# `test-release-check.sh` deliberately never does -- its stub exits 1 so the
# gate takes the documented skip. Here the gate has to actually pass, because
# what is under test is what happens *after* it does.
#
# Usage:
#   bash scripts/test-release-publish.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Two interpreters, selected the way the neighbouring scripts select them: this
# layer parses YAML and needs PyYAML, the fixture layer edits JSON and needs
# only stdlib. A box can carry a `python3` without PyYAML beside a `python` with
# it, so the first is chosen by capability and the second by name.
PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import yaml' >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done

command -v python3 >/dev/null 2>&1 && PYJSON=python3 || PYJSON=python

fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }

# ------------------------------------------------------------------ static
scan_publish_workflow() {
  "$PY" - <<'PY'
import pathlib, sys, yaml

PUBLISH = pathlib.Path(".github/workflows/release-publish.yml")
AUDIT = pathlib.Path(".github/workflows/release.yml")

findings = []


def fault(message):
    findings.append(message)


def load(path):
    if not path.exists():
        fault(f"{path.as_posix()} does not exist")
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def triggers(document):
    """`on:` is YAML 1.1's boolean true, so safe_load gives the key as True."""
    node = document.get("on", document.get(True))
    if isinstance(node, str):
        return {node}
    return set(node or ())


def writes(permissions):
    """The scopes granted at write, whatever shape the block is written in."""
    if not isinstance(permissions, dict):
        # `permissions: write-all` (or a bare string) grants everything. It is
        # not used here and reading it as "no writes" would be the wrong way to
        # be wrong.
        return {"<all>"} if permissions else set()
    return {scope for scope, level in permissions.items() if level == "write"}


publish = load(PUBLISH)
audit = load(AUDIT)

if publish is not None:
    fired_by = triggers(publish)

    # The whole premise. A workflow that can be started by a tag cannot prevent
    # that tag: the ref exists before the run does.
    if "push" in fired_by:
        fault("release-publish.yml can be started by a push — it would run after the ref exists")
    if "workflow_dispatch" not in fired_by:
        fault("release-publish.yml is not dispatchable — an operator has no way to start it")

    if writes(publish.get("permissions")):
        fault("release-publish.yml grants write at the workflow level — grant it on the job that needs it")

    jobs = publish.get("jobs") or {}
    writers = {name: job for name, job in jobs.items() if writes(job.get("permissions"))}

    if not writers:
        fault("no job in release-publish.yml can write — nothing there could create a tag")
    if len(writers) > 1:
        fault(f"more than one job can write: {sorted(writers)}")

    for name, job in writers.items():
        needs = job.get("needs")
        needs = [needs] if isinstance(needs, str) else list(needs or ())
        if not needs:
            fault(f"job '{name}' can write and waits for nothing")
        for upstream in needs:
            if writes((jobs.get(upstream) or {}).get("permissions")):
                fault(f"job '{name}' waits only on '{upstream}', which can also write")
        if "if" not in job:
            fault(f"job '{name}' can write and is not gated on the confirmation input")
        elif "inputs.confirm" not in str(job["if"]):
            fault(f"job '{name}' is gated on something other than inputs.confirm")
        if writes(job.get("permissions")) - {"contents"}:
            fault(f"job '{name}' grants more than contents: {sorted(writes(job.get('permissions')))}")

    # The step that writes lives in the job that may. Anywhere else it would
    # run without the permission, which fails late and reads as a token problem
    # rather than as the ordering mistake it is.
    for name, job in jobs.items():
        for index, step in enumerate(job.get("steps") or []):
            body = step.get("run") or ""
            if "--publish" in body and name not in writers:
                fault(f"job '{name}' step {index} publishes, but is not the writing job")
            if "publish-release.sh" in body and "--dry-run" not in body and "--publish" not in body:
                fault(f"job '{name}' step {index} runs publish-release.sh with no mode")

    # Every job here grades a commit, and grading needs the whole history and
    # the named commit rather than the dispatch ref.
    for name, job in jobs.items():
        for index, step in enumerate(job.get("steps") or []):
            if not str(step.get("uses", "")).startswith("actions/checkout"):
                continue
            with_ = step.get("with") or {}
            if with_.get("fetch-depth") != 0:
                fault(f"job '{name}' step {index} checks out without fetch-depth: 0")
            if "inputs.sha" not in str(with_.get("ref", "")):
                fault(f"job '{name}' step {index} checks out something other than inputs.sha")

if audit is not None:
    # `release.yml` starts from a tag push, so it is the one workflow here that
    # provably cannot prevent anything. Holding it to read-only is what keeps
    # that true no matter what its steps grow into.
    granted = writes(audit.get("permissions"))
    for name, job in (audit.get("jobs") or {}).items():
        granted |= writes(job.get("permissions"))
    if granted:
        fault(f"release.yml runs on a tag push and can write: {sorted(granted)} — it audits, it does not publish")

for message in findings:
    print(f"  {'FAIL':<6} {message}")
if not findings:
    print(f"  {'ok':<6} release-publish.yml checks in a job that cannot write, then writes in one that waits for it")
    print(f"  {'ok':<6} release-publish.yml cannot be started by a push")
    print(f"  {'ok':<6} release.yml holds no write permission")

sys.exit(1 if findings else 0)
PY
}

echo "static — the publish path cannot start from a tag, and cannot write before it checks"

if [ -z "$PY" ]; then
  note FAIL "no python with PyYAML — the workflows were not parsed"
  echo "         Install it (python -m pip install pyyaml) rather than skipping:"
  echo "         this is the layer that reads the permission blocks."
  fail=1
else
  scan_publish_workflow || fail=1
fi

# --------------------------------------------------------------- behaviour
echo
echo "behaviour — publish-release.sh refuses before it writes"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# The stub. It records every invocation and answers check 6 in the affirmative,
# so the gate passes and what happens next is what is being measured. `--jq` is
# consumed rather than honoured: the one read `check-release.sh` makes asks for
# a count, and a count is what this prints.
GH_LOG="$TMP/gh-calls.log"
mkdir -p "$TMP/bin"
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$GH_LOG"
case "\$1" in
  auth) exit 0 ;;
  api)
    for arg in "\$@"; do
      [ "\$arg" = "--method" ] && { echo '{"sha":"stub","ref":"stub","html_url":"stub"}'; exit 0; }
    done
    echo 1
    exit 0
    ;;
esac
exit 0
STUB
chmod +x "$TMP/bin/gh"
: > "$GH_LOG"

# The canary. Every assertion below about a write *not* happening is free if the
# log could never have been written to, and an unwritable temp directory would
# pass all of them.
PATH="$TMP/bin:$PATH" gh api --method POST canary >/dev/null 2>&1 || true
if grep -q -- "--method POST canary" "$GH_LOG" 2>/dev/null; then
  note ok "fixture: the stub records a write, so asserting none happened means something"
else
  note FAIL "fixture: the stub recorded nothing — every no-write assertion below is vacuous"
  fail=1
fi
: > "$GH_LOG"

# The fixture, built rather than cloned: a clone of this repository exceeds
# MAX_PATH on Windows, and `checks` runs this on windows-latest.
FIXTURE="$TMP/fixture"
mkdir -p "$FIXTURE/.claude-plugin" "$FIXTURE/scripts"
cp .claude-plugin/plugin.json .claude-plugin/marketplace.json "$FIXTURE/.claude-plugin/"
cp .version-bump.json RELEASE-NOTES.md "$FIXTURE/"
cp scripts/check-release.sh scripts/bump-version.sh scripts/publish-release.sh "$FIXTURE/scripts/"

PACK="$("$PYJSON" -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["name"])')"
FIXTURE_VERSION="$("$PYJSON" -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])')"
FIXTURE_TAG="${PACK}--v${FIXTURE_VERSION}"

git -C "$FIXTURE" -c init.defaultBranch=main init -q
git -C "$FIXTURE" symbolic-ref HEAD refs/heads/main
# The repository root pins `eol=lf`; a fixture built by hand inherits whatever
# `core.autocrlf` the box has, and a shell script checked out with CRLF fails as
# `$'\r': command not found`, which reads as the script being broken.
git -C "$FIXTURE" config core.autocrlf false
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "the release commit"
RELEASED="$(git -C "$FIXTURE" rev-parse HEAD)"
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$RELEASED"

# A pack that has released before. Without this the fixture is a repository
# where nothing was ever tagged, and HEAD mode's already-released check reports
# `SKIP — cannot tell an unreleased version from an unfetched tag`, which
# `--strict` makes fatal: every case below would fail for a reason that has
# nothing to do with what it is testing. That is the gate behaving correctly on
# an unrealistic subject, and the repair belongs here rather than in a looser
# invocation.
git -C "$FIXTURE" tag "${PACK}--v0.0.1" "$RELEASED"

# `origin` points at the fixture itself, so `git ls-remote` answers from a real
# remote without anything being pushed anywhere.
git -C "$FIXTURE" remote add origin "$FIXTURE"

run_publish() {
  out="$(cd "$FIXTURE" && PATH="$TMP/bin:$PATH" RELEASE_SHA="$1" RELEASE_VERSION="$2" \
    bash "$FIXTURE/scripts/publish-release.sh" "$3" 2>&1)" && rc=0 || rc=$?
}

SHORT="$(git -C "$FIXTURE" rev-parse --short "$RELEASED")"

# The pass direction first: if this does not work, every refusal below is a
# script that refuses everything and proves nothing.
: > "$GH_LOG"
run_publish "$RELEASED" "$FIXTURE_VERSION" --dry-run
if [ "$rc" -ne 0 ]; then
  note FAIL "--dry-run on a good commit — exit $rc, expected 0"
  printf '%s\n' "$out" | sed 's/^/         /'
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "publish $FIXTURE_TAG at $SHORT"; then
  note FAIL "--dry-run — did not name $FIXTURE_TAG at $SHORT"
  fail=1
elif grep -q -- "--method" "$GH_LOG"; then
  note FAIL "--dry-run made a call that writes: $(grep -m1 -- '--method' "$GH_LOG")"
  fail=1
else
  note ok "--dry-run on $SHORT — publishable as $FIXTURE_TAG, and wrote nothing"
fi

# Each of these is a distinct way for the dispatcher and the commit to disagree,
# and each must be refused before the gate is even reached — exit 2, the code
# this repository reserves for input that did not parse rather than a check that
# failed.
refusal_case() {
  local label="$1" sha="$2" version="$3" want="$4" expect_rc="$5"
  : > "$GH_LOG"
  run_publish "$sha" "$version" --dry-run
  if [ "$rc" -ne "$expect_rc" ]; then
    note FAIL "$label — exit $rc, expected $expect_rc"
    printf '%s\n' "$out" | sed 's/^/         /'
    fail=1
  elif ! printf '%s\n' "$out" | grep -qF "$want"; then
    note FAIL "$label — refused, but not for the stated reason"
    printf '%s\n' "$out" | sed 's/^/         /'
    fail=1
  elif grep -q -- "--method" "$GH_LOG"; then
    note FAIL "$label — refused and still made a call that writes"
    fail=1
  else
    note ok "$label"
  fi
}

refusal_case "a ref name where a SHA belongs" \
  "main" "$FIXTURE_VERSION" "not lowercase hex" 2
refusal_case "an abbreviated SHA" \
  "$SHORT" "$FIXTURE_VERSION" "expected 40" 2
refusal_case "an uppercased SHA" \
  "$(printf '%s' "$RELEASED" | tr 'a-f' 'A-F')" "$FIXTURE_VERSION" "not lowercase hex" 2
refusal_case "a well-formed SHA no commit carries" \
  "0000000000000000000000000000000000000000" "$FIXTURE_VERSION" "no commit" 2
refusal_case "the operator's version disagrees with the commit's" \
  "$RELEASED" "9.9.9" "one of them is the wrong commit" 2

# A commit that is not what is checked out. Every check here reads `$SHA`
# through `git show`, but the gate grades `git rev-parse HEAD`, and if those are
# two commits the script reports on one while the gate blesses the other.
: > "$FIXTURE/later.txt"
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "after the release commit"
DESCENDANT="$(git -C "$FIXTURE" rev-parse HEAD)"
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$DESCENDANT"

if [ "$RELEASED" != "$DESCENDANT" ]; then
  note ok "fixture: $(git -C "$FIXTURE" rev-parse --short "$DESCENDANT") is a later commit than $SHORT"
else
  note FAIL "fixture: the two commits are one — the assertions below prove nothing"
  fail=1
fi

refusal_case "a commit that is not the one checked out" \
  "$RELEASED" "$FIXTURE_VERSION" "check out the commit being released" 2

# And the gate's own verdict, which is a different exit code because it is a
# different kind of answer: the input parsed, the checks ran, and one failed.
# HEAD is now a commit `main` has moved past in the only sense that matters —
# it is not the tip — which HEAD mode refuses.
git -C "$FIXTURE" -c advice.detachedHead=false checkout -q "$RELEASED"
refusal_case "a commit main has moved past" \
  "$RELEASED" "$FIXTURE_VERSION" "release gate refused" 1
git -C "$FIXTURE" checkout -q main

# Already published, in the two ways that differ. A local ref is what this clone
# knows; the remote is what decides, and a clone that never fetched tags has the
# first without the second.
git -C "$FIXTURE" tag "$FIXTURE_TAG" "$RELEASED"
git -C "$FIXTURE" -c advice.detachedHead=false checkout -q "$RELEASED"
refusal_case "a version already tagged here" \
  "$RELEASED" "$FIXTURE_VERSION" "already exists locally" 2

CONSUMER="$TMP/consumer"
git clone -q --no-tags "$FIXTURE" "$CONSUMER" 2>/dev/null
git -C "$CONSUMER" -c advice.detachedHead=false checkout -q "$RELEASED"
if [ -z "$(git -C "$CONSUMER" tag --list)" ]; then
  note ok "fixture: the clone has no tags, so the local check cannot be what refuses"
else
  note FAIL "fixture: the clone fetched tags — the remote assertion below is not about the remote"
  fail=1
fi

: > "$GH_LOG"
out="$(cd "$CONSUMER" && PATH="$TMP/bin:$PATH" RELEASE_SHA="$RELEASED" RELEASE_VERSION="$FIXTURE_VERSION" \
  bash "$CONSUMER/scripts/publish-release.sh" --dry-run 2>&1)" && rc=0 || rc=$?
if [ "$rc" -ne 2 ]; then
  note FAIL "a version already published on origin — exit $rc, expected 2"
  printf '%s\n' "$out" | sed 's/^/         /'
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "already exists on origin"; then
  note FAIL "a version already published on origin — refused, but not for the stated reason"
  printf '%s\n' "$out" | sed 's/^/         /'
  fail=1
else
  note ok "a version already published on origin, in a clone that never fetched it"
fi

# The remote that cannot be reached. Nothing and unreachable return the same
# empty output, and only one of them is safe to publish over — this is the
# shape that produced two earlier failures in this subsystem, so it gets an
# assertion rather than a comment.
git -C "$CONSUMER" remote set-url origin "$TMP/no-such-remote.git"
: > "$GH_LOG"
out="$(cd "$CONSUMER" && PATH="$TMP/bin:$PATH" RELEASE_SHA="$RELEASED" RELEASE_VERSION="$FIXTURE_VERSION" \
  bash "$CONSUMER/scripts/publish-release.sh" --dry-run 2>&1)" && rc=0 || rc=$?
if [ "$rc" -ne 2 ]; then
  note FAIL "an unreachable origin — exit $rc, expected 2"
  printf '%s\n' "$out" | sed 's/^/         /'
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "not the same as it being unpublished"; then
  note FAIL "an unreachable origin — refused, but not as an unanswered question"
  printf '%s\n' "$out" | sed 's/^/         /'
  fail=1
else
  note ok "an unreachable origin — refused rather than read as 'not published'"
fi

# No mode at all. The two modes differ by whether they write, so a default is a
# choice nobody made about a remote.
: > "$GH_LOG"
out="$(cd "$FIXTURE" && PATH="$TMP/bin:$PATH" RELEASE_SHA="$RELEASED" RELEASE_VERSION="$FIXTURE_VERSION" \
  bash "$FIXTURE/scripts/publish-release.sh" 2>&1)" && rc=0 || rc=$?
if [ "$rc" -ne 2 ]; then
  note FAIL "no mode given — exit $rc, expected 2"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "no mode given"; then
  note FAIL "no mode given — refused, but not for the stated reason"
  fail=1
else
  note ok "no mode given — neither checked nor wrote"
fi

# ------------------------------------------------------------------ settings
# The ruleset is the only thing that makes the workflow above the *sole* route
# to a tag, and it lives in GitHub's settings rather than here. The JSON in
# `.github/rulesets/` is that ruleset as a reviewable file: GitHub imports it,
# and GitHub never reads it from this repository, so nothing keeps the two in
# step except somebody re-importing after a change.
#
# What is checkable here is narrower and still worth having: that the file says
# what the documentation claims it says, and that its pattern still matches the
# pack it is protecting. A rename would otherwise leave a ruleset guarding a tag
# namespace nothing publishes into, which looks identical to a ruleset that
# works right up until the release that needs it.
echo
echo "settings — the documented ruleset matches the pack it protects"

RULESET=".github/rulesets/dovetail-release-tags.json"

if [ ! -f "$RULESET" ]; then
  note FAIL "$RULESET is missing — the ruleset AGENTS.md describes has no file"
  fail=1
else
  ruleset_report="$("$PYJSON" - "$RULESET" .claude-plugin/plugin.json <<'PY'
import json, sys

ruleset = json.load(open(sys.argv[1], encoding="utf-8"))
pack = json.load(open(sys.argv[2], encoding="utf-8"))["name"]
faults = []

if ruleset.get("target") != "tag":
    faults.append(f"target is {ruleset.get('target')!r}, not 'tag'")
if ruleset.get("enforcement") != "active":
    faults.append(f"enforcement is {ruleset.get('enforcement')!r} — a ruleset that is not active prevents nothing")

wanted = f"refs/tags/{pack}--v*"
include = (ruleset.get("conditions") or {}).get("ref_name", {}).get("include", [])
if wanted not in include:
    faults.append(f"does not target {wanted} — this pack's tags are unprotected")

types = {rule.get("type") for rule in ruleset.get("rules") or []}
for required in ("creation", "update", "deletion"):
    if required not in types:
        faults.append(f"no '{required}' rule — that route to a tag is open")

# An actor id of 0 is the shape of a placeholder somebody meant to fill in, and
# importing one grants bypass to nothing while looking configured. An empty list
# is the honest starting state: it fails closed, and AGENTS.md says to add the
# App after import.
for actor in ruleset.get("bypass_actors") or []:
    if not actor.get("actor_id"):
        faults.append("a bypass actor has no actor_id — that is a placeholder, not an identity")

print("\n".join(faults))
PY
)"

  if [ -n "$ruleset_report" ]; then
    while IFS= read -r line; do
      [ -n "$line" ] && { note FAIL "$RULESET: $line"; fail=1; }
    done <<< "$ruleset_report"
  else
    note ok "$RULESET restricts creation, update and deletion of ${PACK}--v* and is active"
  fi
fi

echo
[ "$fail" -eq 0 ] && echo "Release-publish tests passed." || echo "Release-publish tests FAILED."
exit "$fail"

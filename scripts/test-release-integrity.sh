#!/usr/bin/env bash
#
# test-release-integrity.sh — prove the verifier never reports security it did
# not establish.
#
# `verify-release.sh` exists to answer one question honestly, and there is
# exactly one way for it to fail at that: report a pass over a check that did not
# run. Every other defect is visible — a wrong message is read, a wrong exit code
# breaks a caller — but a run that prints "Release verification passed." after
# skipping the only check that mattered looks identical to a run that verified
# something, and it looks that way in the place the answer gets quoted from.
#
# So the assertions here are mostly negative, and negative assertions are the
# ones that pass when the mechanism is broken. Each section fires a canary first:
# a fixture-state check proving the thing under test is really in the state the
# assertion assumes, so "it never said passed" cannot be bought by the tag not
# existing, or the signature block not being there, or the script never having
# run at all.
#
# Four layers, checked apart because they fail apart:
#
#   no verdict  input the script cannot grade — no tag, an unknown flag, a tag
#               this clone has no ref for, an artifact directory that is not
#               there. Each must exit 2 and grade nothing, because "I could not
#               look" and "I looked and it was fine" are the two answers this
#               whole subsystem exists to keep apart.
#   the object  the subject is the tag object, not the commit under it.
#               `check-release.sh` resolves a tag with `git rev-list -n 1`, which
#               reaches the commit through an annotated object and a lightweight
#               ref alike; that erasure is correct there and fatal here, so this
#               pins that a lightweight ref is refused rather than silently
#               graded as though it were a tag object.
#   the trust   the load-bearing layer. A signature block whose key this clone
#               does not hold must never reach "passed", with or without
#               `--strict`. The fixture is an annotated tag object carrying a
#               signature block and a `gpg.program` that answers "No public key",
#               which is the shape of every real consumer who has fetched a
#               signed tag and imported nobody's key.
#   artifacts   a checksum manifest is graded against the bytes on disk, a
#               missing file in it is a failure rather than a skip, and an empty
#               manifest is refused instead of passing for having no faults.
#
# Nothing here touches this repository. Every tag, ref, commit and config write
# happens inside one `mktemp -d` that is removed on exit. No tag in this
# repository or on any remote is created, moved, signed or deleted, and the
# signature blocks below are literal filler bytes rather than signatures — which
# is the point: what is under test is that filler shaped like a signature is not
# mistaken for one.
#
# Usage:
#   bash scripts/test-release-integrity.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Built rather than cloned, for the reason `test-release-check.sh` records: a
# clone of this repository exits 128 on Windows on MAX_PATH, and a clone's
# refs are frozen at clone time. `core.autocrlf false` because a bash script
# checked out with CRLF fails as `$'\r': command not found`, which reads as the
# verifier being broken rather than as the fixture being wrong.
build_repo() {   # build_repo <dir>
  local dir="$1"
  mkdir -p "$dir/scripts"
  git -C "$dir" -c init.defaultBranch=main init -q
  git -C "$dir" symbolic-ref HEAD refs/heads/main
  git -C "$dir" config core.autocrlf false
  # Emptied locally rather than left to whatever the box has. A developer who
  # signs their own work has this set globally, the fixture would inherit it,
  # and the ssh leg below — whose whole subject is having nothing to judge a
  # signature against — would quietly stop testing that.
  git -C "$dir" config gpg.ssh.allowedSignersFile ""
  cp scripts/verify-release.sh "$dir/scripts/"
  printf 'fixture\n' > "$dir/content.txt"
  git -C "$dir" add -A
  git -C "$dir" -c user.name=t -c user.email=t@e commit -q -m "the tree under test"
}

# An annotated tag object carrying a signature block, written straight into the
# object store. `git tag -s` would need a key, and a key is exactly what a test
# asserting "this clone cannot verify it" must not have.
write_signed_tag() {   # write_signed_tag <dir> <tag> <commit> <kind>
  local dir="$1" tag="$2" commit="$3" kind="$4" obj
  obj="$(printf 'object %s\ntype commit\ntag %s\ntagger t <t@e> 0 +0000\n\nthe message\n-----BEGIN %s SIGNATURE-----\n\nbm90IGEgc2lnbmF0dXJl\n-----END %s SIGNATURE-----\n' \
    "$commit" "$tag" "$kind" "$kind" | git -C "$dir" hash-object -t tag -w --stdin)"
  git -C "$dir" update-ref "refs/tags/$tag" "$obj"
}

run_verify() {   # run_verify <dir> [args...]
  local dir="$1"
  shift
  out="$(cd "$dir" && bash scripts/verify-release.sh "$@" 2>&1)" && rc=0 || rc=$?
}

# `--` before the needle: several of the strings asserted below start with a
# dash, and grep reads those as its own options.
said() { printf '%s\n' "$out" | grep -qF -- "$1"; }

# ------------------------------------------------------------------- no verdict
echo
echo "no verdict — input the script cannot grade is refused, not graded"

CANARY="$TMP/canary"
bash -c ": ignored\$(touch '$CANARY')" >/dev/null 2>&1 || true
if [ -e "$CANARY" ]; then
  note ok "canary fires when text is evaluated"
  rm -f "$CANARY"
else
  note FAIL "canary cannot fire — every assertion below would pass vacuously"
  fail=1
fi

REPO="$TMP/repo"
build_repo "$REPO"
COMMIT="$(git -C "$REPO" rev-parse HEAD)"

git -C "$REPO" tag lightweight "$COMMIT"
git -C "$REPO" -c user.name=t -c user.email=t@e tag -a -m "annotated" plain "$COMMIT"
write_signed_tag "$REPO" signed "$COMMIT" PGP

# Fixture canary. Every assertion in the two layers below is about which of these
# three shapes the script was handed, so if they are not actually three different
# shapes, the assertions prove nothing.
LIGHT_TYPE="$(git -C "$REPO" cat-file -t refs/tags/lightweight)"
PLAIN_TYPE="$(git -C "$REPO" cat-file -t refs/tags/plain)"
SIGNED_TYPE="$(git -C "$REPO" cat-file -t refs/tags/signed)"
if [ "$LIGHT_TYPE" = commit ] && [ "$PLAIN_TYPE" = tag ] && [ "$SIGNED_TYPE" = tag ] &&
   git -C "$REPO" cat-file -p refs/tags/signed | grep -qF -- "-----BEGIN PGP SIGNATURE-----" &&
   ! git -C "$REPO" cat-file -p refs/tags/plain | grep -qF -- "-----BEGIN PGP SIGNATURE-----"; then
  note ok "fixture: lightweight is a commit, plain and signed are tag objects, one carries a block"
else
  note FAIL "fixture: the three tags are not three different shapes — the assertions below prove nothing"
  fail=1
fi

no_verdict_case() {   # no_verdict_case <label> <want-substring> [args...]
  local label="$1" want="$2"
  shift 2
  run_verify "$REPO" "$@"
  if [ "$rc" -ne 2 ]; then
    note FAIL "$label — exit $rc, expected 2"
    fail=1
  elif ! said "$want"; then
    note FAIL "$label — did not say '$want'"
    fail=1
  elif said "Release verification passed."; then
    note FAIL "$label — refused and still reported a pass"
    fail=1
  else
    note ok "$label"
  fi
}

no_verdict_case "no tag named"            "no tag given"
no_verdict_case "unknown flag"            "usage:"                     --bogus plain
no_verdict_case "tag with no ref here"    "cannot resolve"             dovetail--v0.0.0-absent
no_verdict_case "--artifacts with no dir" "nothing was read"           --artifacts "$TMP/not-a-directory" plain
no_verdict_case "--artifacts with no value" "--artifacts needs a directory" plain --artifacts

# The script is a reader. A run that leaves the repository different is a defect
# whatever it printed, and the canary proves a difference would be seen.
STATE_BEFORE="$(git -C "$REPO" status --porcelain; git -C "$REPO" for-each-ref)"
run_verify "$REPO" plain
printf 'written\n' > "$REPO/canary-write.txt"
STATE_DIRTIED="$(git -C "$REPO" status --porcelain; git -C "$REPO" for-each-ref)"
rm -f "$REPO/canary-write.txt"
STATE_AFTER="$(git -C "$REPO" status --porcelain; git -C "$REPO" for-each-ref)"
if [ "$STATE_BEFORE" = "$STATE_DIRTIED" ]; then
  note FAIL "canary: a write to the fixture was not detected — the no-write assertion proves nothing"
  fail=1
elif [ "$STATE_BEFORE" = "$STATE_AFTER" ]; then
  note ok "a run leaves no file and no ref behind"
else
  note FAIL "the run changed the repository"
  fail=1
fi

# ------------------------------------------------------------------- the object
echo
echo "the object — the tag object is the subject, not the commit under it"

run_verify "$REPO" lightweight
if [ "$rc" -ne 1 ]; then
  note FAIL "lightweight — exit $rc, expected 1"
  fail=1
elif ! said "is a lightweight ref"; then
  note FAIL "lightweight — did not name the object type"
  fail=1
elif said "Release verification passed."; then
  note FAIL "lightweight — graded a bare ref as a pass"
  fail=1
else
  note ok "a lightweight ref is refused rather than graded as a tag object"
fi

run_verify "$REPO" plain
if [ "$rc" -ne 1 ]; then
  note FAIL "unsigned annotated — exit $rc, expected 1"
  fail=1
elif ! said "is an annotated tag object"; then
  note FAIL "unsigned annotated — did not recognise the tag object"
  fail=1
elif ! said "is unsigned"; then
  note FAIL "unsigned annotated — did not say it is unsigned"
  fail=1
else
  note ok "an annotated tag with no signature is a definite negative, not a skip"
fi

# -------------------------------------------------------------------- the trust
echo
echo "the trust — a signature this clone cannot check is never a pass"

# `gpg.program` rather than a PATH stub: git resolves it per-repository, so the
# fixture carries its own answer and the assertion does not depend on the order
# of directories in PATH on whichever runner this is.
GPG_STUB="$TMP/no-key-gpg"
cat > "$GPG_STUB" <<'STUB'
#!/usr/bin/env bash
echo "gpg: Can't check signature: No public key" >&2
exit 2
STUB
chmod +x "$GPG_STUB"
git -C "$REPO" config gpg.program "$GPG_STUB"

# Fixture canary: the stub has to actually be reached, or "it did not verify" is
# bought by git never asking anything. Captured before grepping rather than
# piped into it, because `set -o pipefail` is in force and `git verify-tag`
# exits non-zero here by design — piping would report the probe's own expected
# failure as the canary failing.
STUB_PROBE="$(git -C "$REPO" verify-tag signed 2>&1)" || true
if printf '%s\n' "$STUB_PROBE" | grep -qF "No public key"; then
  note ok "fixture: the stub is reached, so an unverifiable signature is really unverifiable"
else
  note FAIL "fixture: git never consulted the stub — the assertions below prove nothing"
  fail=1
fi

run_verify "$REPO" signed
if [ "$rc" -ne 2 ]; then
  note FAIL "unverifiable signature — exit $rc, expected 2 (no verdict)"
  fail=1
elif said "Release verification passed."; then
  note FAIL "unverifiable signature — reported a pass over a check that did not run"
  fail=1
elif ! said "INCOMPLETE"; then
  note FAIL "unverifiable signature — the verdict line did not say the run was incomplete"
  fail=1
elif ! said "unverifiable here"; then
  note FAIL "unverifiable signature — did not say why nothing was established"
  fail=1
elif said "verified against a key"; then
  note FAIL "unverifiable signature — claimed a key verified it"
  fail=1
else
  note ok "a signature with no trusted key ends INCOMPLETE at exit 2, never passed"
fi

run_verify "$REPO" --strict signed
if [ "$rc" -ne 1 ]; then
  note FAIL "--strict unverifiable — exit $rc, expected 1"
  fail=1
elif said "Release verification passed."; then
  note FAIL "--strict unverifiable — reported a pass"
  fail=1
else
  note ok "--strict turns the undetermined verdict into a failure"
fi

# Which binary is missing is read from `gpg.program`, not assumed to be named
# `gpg`. This pins a real defect: the check asked whether `gpg` was on PATH
# while git asks `gpg.program` what to run, so a clone pointing at gpg2 or a
# wrapper was reported as having no gpg — a "could not ask" invented out of
# nothing, on a box that could have answered. Pointing it at a name that is
# certainly absent makes the assertion independent of whether this runner
# happens to ship gpg.
git -C "$REPO" config gpg.program "$TMP/absent-signing-program"
run_verify "$REPO" signed
if [ "$rc" -ne 2 ]; then
  note FAIL "absent gpg.program — exit $rc, expected 2"
  fail=1
elif ! said "absent-signing-program is not installed"; then
  note FAIL "absent gpg.program — named the wrong binary as missing"
  fail=1
elif said "Release verification passed."; then
  note FAIL "absent gpg.program — reported a pass"
  fail=1
else
  note ok "the missing binary is the one gpg.program names, not one called gpg"
fi
git -C "$REPO" config gpg.program "$GPG_STUB"

# An ssh signature with no allowed-signers file is the same state reached by a
# different route, and it must not fall through to gpg and be graded there.
write_signed_tag "$REPO" signed-ssh "$COMMIT" SSH
run_verify "$REPO" signed-ssh
if [ "$rc" -ne 2 ]; then
  note FAIL "ssh signature, no allowed-signers — exit $rc, expected 2"
  fail=1
elif ! said "allowedSignersFile"; then
  note FAIL "ssh signature, no allowed-signers — did not name what is missing"
  fail=1
elif said "Release verification passed."; then
  note FAIL "ssh signature, no allowed-signers — reported a pass"
  fail=1
else
  note ok "an ssh signature with nothing to judge it against is undetermined, not passed"
fi

# ---------------------------------------------------------------- the artifacts
echo
echo "the artifacts — the manifest is graded against the bytes on disk"

ART="$TMP/artifacts"
mkdir -p "$ART"
printf 'payload one\n' > "$ART/one.tgz"
printf 'payload two\n' > "$ART/two.tgz"

digest_for() {   # digest_for <file>
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum -b "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 -b "$1" | cut -d' ' -f1
  else
    python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
  fi
}

ONE="$(digest_for "$ART/one.tgz")"
TWO="$(digest_for "$ART/two.tgz")"

# Fixture canary: two different payloads must have two different digests, or a
# mismatch assertion below could be satisfied by everything hashing the same.
if [ -n "$ONE" ] && [ -n "$TWO" ] && [ "$ONE" != "$TWO" ]; then
  note ok "fixture: the two payloads hash differently"
else
  note FAIL "fixture: digests are empty or identical — the manifest assertions prove nothing"
  fail=1
fi

printf '%s *one.tgz\n%s *two.tgz\n' "$ONE" "$TWO" > "$ART/SHA256SUMS"

run_verify "$REPO" --artifacts "$ART" plain
if said "does not match SHA256SUMS"; then
  note FAIL "matching manifest — reported a mismatch against correct digests"
  fail=1
elif ! said "match the bytes in"; then
  note FAIL "matching manifest — did not confirm the files match"
  fail=1
else
  note ok "a manifest whose digests match is reported as matching"
fi

# Absence of the signature over the manifest, and of an SBOM, are findings in
# their own right: a manifest anybody can rewrite proves the bytes are
# self-consistent and nothing about where they came from.
if said "SHA256SUMS is unsigned" && said "no SBOM or provenance document"; then
  note ok "an unsigned manifest and a missing SBOM are named as findings"
else
  note FAIL "an unsigned manifest or missing SBOM passed unremarked"
  fail=1
fi

printf '%s *one.tgz\n%s *two.tgz\n' "$ONE" "$ONE" > "$ART/SHA256SUMS"
run_verify "$REPO" --artifacts "$ART" plain
if [ "$rc" -ne 1 ]; then
  note FAIL "mismatched manifest — exit $rc, expected 1"
  fail=1
elif ! said "two.tgz does not match SHA256SUMS"; then
  note FAIL "mismatched manifest — did not name the file that disagrees"
  fail=1
elif said "Release verification passed."; then
  note FAIL "mismatched manifest — reported a pass"
  fail=1
else
  note ok "a digest that disagrees with the bytes is named and fails"
fi

printf '%s *one.tgz\n%s *absent.tgz\n' "$ONE" "$TWO" > "$ART/SHA256SUMS"
run_verify "$REPO" --artifacts "$ART" plain
if [ "$rc" -ne 1 ]; then
  note FAIL "manifest naming a missing file — exit $rc, expected 1"
  fail=1
elif ! said "no such file"; then
  note FAIL "manifest naming a missing file — did not say the file is absent"
  fail=1
else
  note ok "a file listed and not shipped is a failure, not a skip"
fi

: > "$ART/SHA256SUMS"
run_verify "$REPO" --artifacts "$ART" plain
if [ "$rc" -ne 1 ]; then
  note FAIL "empty manifest — exit $rc, expected 1"
  fail=1
elif ! said "is empty"; then
  note FAIL "empty manifest — did not say it lists nothing"
  fail=1
elif said "Release verification passed."; then
  note FAIL "empty manifest — passed for having no faults to find"
  fail=1
else
  note ok "an empty manifest is refused rather than passing vacuously"
fi

rm -f "$ART/SHA256SUMS"
run_verify "$REPO" --artifacts "$ART" plain
if [ "$rc" -ne 1 ]; then
  note FAIL "no manifest — exit $rc, expected 1"
  fail=1
elif ! said "no SHA256SUMS in"; then
  note FAIL "no manifest — did not say the manifest is missing"
  fail=1
else
  note ok "artifacts shipped with no manifest at all is a failure"
fi

# Control. The section is worth nothing if the script refuses everything, so one
# run that reaches a clean artifact verdict has to exist. It uses a tag whose
# signature the fixture can check, which nothing here has — so the control is
# scoped to the artifact layer and says so.
printf '%s *one.tgz\n' "$ONE" > "$ART/SHA256SUMS"
printf 'not a real signature\n' > "$ART/SHA256SUMS.asc"
printf '{}\n' > "$ART/dovetail.spdx.json"
run_verify "$REPO" --artifacts "$ART" plain
if said "does not match" || said "no SHA256SUMS in" || said "is unsigned — it shows" ||
   said "no SBOM or provenance document"; then
  note FAIL "control — a complete artifact set still drew an artifact finding"
  fail=1
elif ! said "match the bytes in"; then
  note FAIL "control — a complete artifact set did not verify"
  fail=1
else
  note ok "control: a manifest, a detached signature and an SBOM together draw no artifact finding"
fi

echo
[ "$fail" -eq 0 ] && echo "Release-integrity tests passed." || echo "Release-integrity tests FAILED."
exit "$fail"

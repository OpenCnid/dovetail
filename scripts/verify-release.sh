#!/usr/bin/env bash
#
# verify-release.sh — report what can be proved about a tag that already shipped.
#
# `check-release.sh` is the gate. It asks "should this commit be released?", and
# to answer it resolves a tag to its commit with `git rev-list -n 1` — which
# reaches the commit through an annotated tag object and through a lightweight
# ref alike, because the commit is the thing it grades. That resolution is
# correct there and it erases exactly what this script is about: the tag object
# itself, and whether anything vouches for it.
#
# So the two are not two entrypoints to one question. The gate runs before a
# release and decides whether it may happen. This runs after one, on a clone
# that fetched the tag, and answers a consumer's question instead: given this
# ref, what is actually established, and by what.
#
# The distinction it exists to hold is between three states that a single
# "verified / not verified" answer collapses into one:
#
#   asked, and got a yes    the signature checked out against a trust root this
#                           clone actually has
#   asked, and got a no     there is no signature, or one that failed — a real
#                           negative, and the release is what it is
#   could not ask           a signature is present and nothing here can judge it:
#                           no gpg, no public key, no allowed-signers file
#
# The third is the one that matters, because it is the one that a check written
# to return a boolean reports as a pass. A tag carrying a signature block nobody
# can verify is not a signed release; it is bytes shaped like one.
#
# So the verdict here is three-way rather than two-way, and that is a deliberate
# departure from `check-release.sh`, which reports the same third state as a
# `SKIP` that leaves the exit code at 0 unless `--strict` is passed. That
# contract is right for a gate: the SKIP is printed, a human is reading, and the
# release is blocked by other means. It is wrong for this script, because this
# script's entire output is a claim about what is established, and a run that
# ends "Release verification passed." after establishing nothing is the overclaim
# it exists to refuse. An undetermined check therefore ends the run at
# INCOMPLETE and exit 2 — no verdict, which is what actually happened — and
# never at passed. `--strict` collapses that 2 into a 1 for callers that want a
# single non-zero.
#
# It writes nothing, anywhere. It creates no tag, moves no ref, signs nothing,
# fetches nothing, and makes no network call. Every question it asks is a read.
#
# On what it will say about this pack today, so nobody reads a green run as more
# than it is: measured 2026-08-06 on git-bash 5.2.37(msys), Windows 10, all five
# published tags (`dovetail--v0.2.0` through `dovetail--v0.4.1`) are annotated
# tag objects carrying no signature block at all, and the publish route cannot
# produce one — `publish-release.sh` creates the tag through
# `gh api --method POST repos/{owner}/{repo}/git/tags`, which has no signing
# input. So check 3 is a real negative here rather than an undetermined one, and
# it stays that way until the publish route changes. `docs/release-integrity.md`
# is where that change is written down.
#
# Exit codes follow the house contract: 0 pass, 1 a check ran and failed, 2 no
# verdict. Three routes reach 2 — the input did not parse, the subject could not
# be reached, or every check that ran came back undetermined and none came back
# a failure.
#
# Usage:
#   bash scripts/verify-release.sh <tag>
#   bash scripts/verify-release.sh --strict <tag>
#   bash scripts/verify-release.sh --artifacts <dir> <tag>

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

USAGE="usage: bash scripts/verify-release.sh [--strict] [--artifacts <dir>] <tag>"

STRICT=0
ARTIFACTS=""
ARTIFACTS_GIVEN=0
TAG=""

# A `for arg in "$@"` loop is the form the other scripts here use, and it cannot
# carry `--artifacts <dir>`: the value would parse as a second positional and
# become the tag. Hence the shift loop. Everything else about the parse matches
# them — unknown flags exit 2, an empty argument is ignored because a workflow
# `env:` that is unset expands to one.
while [ "$#" -gt 0 ]; do
  case "$1" in
    --strict) STRICT=1 ;;
    --artifacts)
      if [ "$#" -lt 2 ]; then
        echo "--artifacts needs a directory" >&2
        echo "$USAGE" >&2
        exit 2
      fi
      ARTIFACTS="$2"
      ARTIFACTS_GIVEN=1
      shift
      ;;
    "") ;;
    -*) echo "$USAGE" >&2; exit 2 ;;
    *) TAG="$1" ;;
  esac
  shift
done

if [ -z "$TAG" ]; then
  echo "no tag given — this reports on a release that already exists" >&2
  echo "to grade a commit before tagging, that is scripts/check-release.sh --head" >&2
  echo "$USAGE" >&2
  exit 2
fi

# The artifact directory is input, and a named-but-absent one is not the same
# evidence as an unnamed one. Unnamed means nobody asked about artifacts; absent
# means somebody did and the answer could not be read. Refusing here keeps the
# second from being reported as the first further down.
if [ "$ARTIFACTS_GIVEN" -eq 1 ] && [ ! -d "$ARTIFACTS" ]; then
  echo "no directory at $ARTIFACTS" >&2
  echo "nothing was read, so there is no verdict about this release's artifacts" >&2
  echo "  gh release download $TAG --dir <dir>   # then ask again" >&2
  exit 2
fi

# The ref has to be here before anything else means anything. An unresolvable
# tag is refused rather than stood in for, because the two readings of an empty
# `refs/tags/` have opposite verdicts and this cannot tell them apart from
# inside — `git clone --no-tags`, `--depth 1` and actions/checkout's default all
# produce a repository where "never published" and "never fetched" look
# identical.
if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "cannot resolve $TAG in this repository" >&2
  echo "no ref refs/tags/$TAG — and this cannot tell a tag that was never made" >&2
  echo "from one this clone never fetched (git clone --no-tags, --depth 1 and" >&2
  echo "actions/checkout's default all leave refs/tags/ empty)." >&2
  echo "  git fetch --tags origin        # then ask again" >&2
  exit 2
fi

SHA="$(git rev-list -n 1 "$TAG")"

fail=0
unknown=0
note() { printf '  %-6s %s\n' "$1" "$2"; }

# An undetermined check is counted rather than ignored, because the count is what
# stops the run ending in "passed". `--strict` promotes it to a failure outright
# and touches nothing else — it never turns a FAIL into a pass, and never
# suppresses output.
undetermined() {
  note SKIP "$1"
  unknown=$((unknown + 1))
  if [ "$STRICT" -eq 1 ]; then
    fail=1
  fi
}

echo "release $TAG at $(git rev-parse --short "$SHA")"
echo

# ---------------------------------------------------------------- 1. the object
# A lightweight tag is a ref pointing straight at the commit. It carries no
# tagger, no message and nowhere to put a signature, so this decides whether
# checks 2 and 3 have a subject at all.
OBJECT_TYPE="$(git cat-file -t "refs/tags/$TAG")"

if [ "$OBJECT_TYPE" = "tag" ]; then
  note ok "$TAG is an annotated tag object"
else
  note FAIL "$TAG is a lightweight ref, not a tag object — nothing to sign, and no tagger recorded"
  fail=1
fi

# ------------------------------------------------------------- 2. the signature
# Read the object rather than asking `git verify-tag` first: verify-tag reports
# "no signature" and "cannot check this signature" through the same non-zero
# exit, and those are the two states this whole script exists to keep apart.
SIGNATURE_KIND=""

# Which binary git would actually run, rather than the name it usually has.
# `git verify-tag` obeys `gpg.program`, so asking whether `gpg` is on PATH
# answers a question about this box that need not be the question about this
# repository — a clone pointing at gpg2, or at a wrapper, would be reported as
# having no gpg at all, which is a "could not ask" invented out of nothing.
GPG_PROGRAM="$(git config --get gpg.program || true)"
[ -n "$GPG_PROGRAM" ] || GPG_PROGRAM=gpg

if [ "$OBJECT_TYPE" = "tag" ]; then
  TAG_BODY="$(git cat-file -p "refs/tags/$TAG")"
  if printf '%s\n' "$TAG_BODY" | grep -qF -- "-----BEGIN PGP SIGNATURE-----"; then
    SIGNATURE_KIND=pgp
  elif printf '%s\n' "$TAG_BODY" | grep -qF -- "-----BEGIN SSH SIGNATURE-----"; then
    SIGNATURE_KIND=ssh
  fi
fi

if [ "$OBJECT_TYPE" != "tag" ]; then
  note FAIL "no signature — a lightweight ref cannot carry one"
  fail=1
elif [ -n "$SIGNATURE_KIND" ]; then
  note ok "$TAG carries a $SIGNATURE_KIND signature block"
else
  note FAIL "$TAG is unsigned — annotation records who typed the message, not who vouches for it"
  fail=1
fi

# ----------------------------------------------------------- 3. the trust root
# Present is not verified, and verified here is not verified anywhere: the
# question is whether *this* clone holds something that judges the signature.
# Where it does not, the honest answer is that the check did not run.
if [ -z "$SIGNATURE_KIND" ]; then
  note SKIP "no signature to verify — check 2 is the finding, not this one"
elif [ "$SIGNATURE_KIND" = ssh ] &&
     [ -z "$(git config --get gpg.ssh.allowedSignersFile || true)" ]; then
  undetermined "ssh signature present and no gpg.ssh.allowedSignersFile here — nothing to judge it against"
elif [ "$SIGNATURE_KIND" = pgp ] && ! command -v "$GPG_PROGRAM" >/dev/null 2>&1; then
  undetermined "pgp signature present and $GPG_PROGRAM is not installed — the signature was NOT checked"
else
  VERIFY_OUT="$(git verify-tag "$TAG" 2>&1)" && VERIFY_RC=0 || VERIFY_RC=$?
  if [ "$VERIFY_RC" -eq 0 ]; then
    # Deliberately not "the release is authentic". A good signature from a key
    # in this keyring says the bytes are intact and names a key; whether that
    # key belongs to whoever may publish this pack is a question about the
    # keyring, which this script did not audit and cannot.
    note ok "signature verified against a key this clone already trusts"
  elif printf '%s\n' "$VERIFY_OUT" |
       grep -qiE "no public key|public key not found|can't check signature|certificate has expired|no principal matched"; then
    undetermined "signature present and unverifiable here — no trusted key for it, so nothing was established"
  else
    # The whole output, indented, rather than a line picked out of it. gpg puts
    # the useful sentence in a different place depending on why it refused, and
    # a message that quotes the wrong line reads as this script malfunctioning
    # rather than as the signature being bad.
    note FAIL "signature did not verify"
    printf '%s\n' "$VERIFY_OUT" | sed 's/^/         /'
    fail=1
  fi
fi

echo

# ---------------------------------------------------------- 4. the digest tool
# Named before the artifact checks so "the manifest disagrees" and "nothing here
# can compute a digest" cannot arrive as the same line.
DIGEST=""
if command -v sha256sum >/dev/null 2>&1; then
  DIGEST=sha256sum
elif command -v shasum >/dev/null 2>&1; then
  DIGEST=shasum
elif command -v python3 >/dev/null 2>&1; then
  DIGEST=python3
elif command -v python >/dev/null 2>&1; then
  DIGEST=python
fi

# Digests are taken over the bytes on disk, which is the only thing a consumer
# receives. That is worth stating because this repository has already been bitten
# the other way: five of six hashes in `docs/self-play/vendor/HASHES.txt` were
# computed against CRLF working copies and verified nowhere else.
digest_of() {
  case "$DIGEST" in
    sha256sum) sha256sum -b "$1" | cut -d' ' -f1 ;;
    shasum)    shasum -a 256 -b "$1" | cut -d' ' -f1 ;;
    python3|python)
      "$DIGEST" -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1" ;;
    *) return 1 ;;
  esac
}

# ------------------------------------------------------------- 5. the artifacts
# Three states again, and the same rule: an unnamed directory means nobody
# asked, which is not a finding about the release.
if [ "$ARTIFACTS_GIVEN" -eq 0 ]; then
  undetermined "no --artifacts <dir> given — nothing was read, so nothing is established about what ships beside the tag"
elif [ -z "$DIGEST" ]; then
  undetermined "no sha256sum, shasum or python here — the manifest was NOT checked"
elif [ ! -f "$ARTIFACTS/SHA256SUMS" ]; then
  note FAIL "no SHA256SUMS in $ARTIFACTS — the release ships bytes and no way to tell whether they arrived intact"
  fail=1
else
  MANIFEST_FAULTS=0
  MANIFEST_LINES=0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    want="${line%% *}"
    named="${line#* }"
    named="${named# }"
    named="${named#\*}"
    MANIFEST_LINES=$((MANIFEST_LINES + 1))
    if [ ! -f "$ARTIFACTS/$named" ]; then
      note FAIL "SHA256SUMS lists $named — no such file in $ARTIFACTS"
      MANIFEST_FAULTS=$((MANIFEST_FAULTS + 1))
      continue
    fi
    if ! got="$(digest_of "$ARTIFACTS/$named")"; then
      note FAIL "could not compute a digest for $named"
      MANIFEST_FAULTS=$((MANIFEST_FAULTS + 1))
      continue
    fi
    if [ "$got" != "$want" ]; then
      note FAIL "$named does not match SHA256SUMS — got $got, expected $want"
      MANIFEST_FAULTS=$((MANIFEST_FAULTS + 1))
    fi
  done < "$ARTIFACTS/SHA256SUMS"

  if [ "$MANIFEST_LINES" -eq 0 ]; then
    note FAIL "SHA256SUMS in $ARTIFACTS is empty — it lists nothing, so it proves nothing"
    fail=1
  elif [ "$MANIFEST_FAULTS" -gt 0 ]; then
    fail=1
  else
    note ok "all $MANIFEST_LINES file(s) in SHA256SUMS match the bytes in $ARTIFACTS"
  fi

  # A checksum manifest anybody can rewrite proves the bytes are self-consistent
  # and nothing about where they came from. The signature over the manifest is
  # what carries origin, so its absence is a finding rather than a detail.
  if [ -f "$ARTIFACTS/SHA256SUMS.asc" ] || [ -f "$ARTIFACTS/SHA256SUMS.sig" ]; then
    note ok "SHA256SUMS carries a detached signature"
  else
    note FAIL "SHA256SUMS is unsigned — it shows the bytes are intact, not that they are ours"
    fail=1
  fi

  # SBOM or provenance attestation. Presence only: reading one and judging its
  # claims is a different tool, and saying otherwise here would be the exact
  # overclaim this script is written against.
  SBOM_FOUND=0
  for candidate in "$ARTIFACTS"/*.spdx.json "$ARTIFACTS"/*.cdx.json \
                   "$ARTIFACTS"/*.intoto.jsonl; do
    if [ -f "$candidate" ]; then
      SBOM_FOUND=1
    fi
  done
  if [ "$SBOM_FOUND" -eq 1 ]; then
    note ok "an SBOM or provenance document ships beside the artifacts (contents not judged here)"
  else
    note FAIL "no SBOM or provenance document in $ARTIFACTS — nothing states what this release is made of"
    fail=1
  fi
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "Release verification FAILED."
  exit 1
fi
if [ "$unknown" -gt 0 ]; then
  # Not a pass, and said in the verdict line rather than only in the SKIPs
  # above, because the last line is the one that gets quoted.
  echo "Release verification INCOMPLETE — $unknown check(s) could not be answered here."
  echo "Nothing above was established by a check that did not run."
  exit 2
fi
echo "Release verification passed."
exit 0

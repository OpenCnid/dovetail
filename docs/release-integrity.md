# Release integrity

`AGENTS.md` "Releasing" is the authority on *whether a release should happen*:
the six checks, the two modes, which commit each one grades, and why the tag is
created after them rather than graded once it has shipped. This document is
about the layer underneath that question — *what a person who received a release
can establish about it*, and by what — and it does not restate the gate. Where
the two meet, this links rather than repeats.

Not to be confused with [`docs/provenance.md`](provenance.md), which records
where each skill's source repository was and at which commit its content
arrived. That is provenance in the archival sense. This is provenance in the
supply-chain sense: signatures, digests and attestations over what ships.

## The three states, and why the distinction is the whole subject

Every check below can come back three ways, and collapsing them into two is the
failure this document exists to prevent:

| state | meaning | verdict |
|---|---|---|
| established | asked, and the evidence answered | `ok` |
| a real negative | asked, and the answer is no | `FAIL`, exit 1 |
| could not ask | the evidence is not readable here | `SKIP`, exit 2 |

A tag carrying a signature block that this clone holds no key for is the third,
not the first. A tool that reports it as a pass has not verified a release; it
has reported that it did not look. `scripts/verify-release.sh` ends such a run at
`INCOMPLETE` and exit 2, never at passed, and `--strict` collapses that 2 into a
1 for callers that want a single non-zero.

## What is established today

Measured 2026-08-06 on git-bash 5.2.37(1)-release (x86_64-pc-msys), git
2.47.1.windows.1, Windows 10, against the five published tags
`dovetail--v0.2.0` … `dovetail--v0.4.1`:

| property | state |
|---|---|
| tags are annotated tag objects | yes, all five |
| tags carry a signature block | no, none of the five |
| a checksum manifest ships with a release | no — the release carries no assets |
| an SBOM or provenance attestation ships | no |
| the tag ruleset exists as a reviewable file | yes, `.github/rulesets/dovetail-release-tags.json` |
| that ruleset is imported and active on GitHub | **unverifiable from here** — see § 3 |

The first two rows are a property of the publish route rather than an oversight
to be patched in the tag: `scripts/publish-release.sh` creates the tag with
`gh api --method POST repos/{owner}/{repo}/git/tags`, and that endpoint has no
signing input. Signing is therefore a change to *how a release is cut*, not a
flag to add to an existing step. § 1 says what the change is.

## 1. Signed-tag verification

**To verify a tag you have fetched:**

```bash
git fetch --tags origin
bash scripts/verify-release.sh dovetail--v0.4.1
```

It reports, in order: whether the ref resolves here at all, whether it is an
annotated tag object or a bare ref, whether a signature block is present, and
whether anything in this clone can judge that signature. It writes nothing,
fetches nothing, and creates no ref.

**What a pass means, and what it does not.** `signature verified against a key
this clone already trusts` says the tagged bytes are intact and names a key it
matched. It does not say that key belongs to somebody entitled to publish this
pack — that is a question about the keyring, which the script does not audit and
cannot. Establishing *whose* key it is means pinning the expected identity
somewhere a verifier can read it, which is the `allowed_signers` file below.

**To make signing possible, in order:**

1. Choose the signing identity. It must be the same identity that publishes, or
   the signature attests to a second party who did not cut the release. Where
   the publisher is a GitHub App (§ 5), an SSH signing key held as an
   environment secret is the tractable form; a personal PGP key held by one
   human is the form that stops working when that human does.
2. Commit an `allowed_signers` file naming the identity, and point verification
   at it, so that "verified" means "verified as ours" rather than "verified as
   someone's":
   ```bash
   git config gpg.ssh.allowedSignersFile .github/allowed_signers
   ```
3. Replace the tag-object creation in `scripts/publish-release.sh`. The REST
   endpoint cannot sign, so the publish job must instead create the object
   locally with `git tag -s` and push the ref — which changes what permissions
   that job needs and what the ruleset must let through. Do not add
   `required_signatures` to the ruleset before this lands (§ 3).
4. Only once tags are signed does adding this to the release gate make sense.
   Until then `scripts/verify-release.sh` is a report, not a gate, and is
   deliberately not wired into `checks.yml` as a blocking step — a check that
   fails on every commit teaches people to ignore it.

## 2. Checksums, SBOM and provenance artifacts

A release currently ships no assets, so there is nothing to hash and the
question does not arise. It arises the moment one does, and the shape is fixed
here so that it is not decided under time pressure during a release.

**Expected artifact set**, for a release that ships assets at all:

| file | what it establishes |
|---|---|
| `SHA256SUMS` | the bytes received are the bytes published |
| `SHA256SUMS.asc` or `.sig` | those digests are ours, not a rewrite |
| `*.spdx.json`, `*.cdx.json` or `*.intoto.jsonl` | what the release is made of, or how it was built |

A manifest without the signature over it proves internal consistency and
nothing about origin — anyone who can replace the artifacts can replace the
manifest. That is why the second row is a finding in its own right rather than a
nicety.

**Generation** belongs in the publishing job, after the gate and before the
release object is created, so that a failure leaves no announced release
pointing at unverified bytes:

```bash
sha256sum -b dist/* > dist/SHA256SUMS
gh release upload "$TAG" dist/SHA256SUMS dist/*
```

**Verification:**

```bash
gh release download dovetail--v0.4.1 --dir ./release-assets
bash scripts/verify-release.sh --artifacts ./release-assets dovetail--v0.4.1
```

**Digests are taken over the bytes on disk**, in binary mode, and this
repository has already paid for getting that wrong once: five of the six hashes
in `docs/self-play/vendor/HASHES.txt` were computed against CRLF working copies
and verified on no fresh clone. `.gitattributes` pins `eol=lf` for tracked
files, but a release asset is not a tracked file — it is whatever the build
wrote — so the manifest must be generated from the same bytes that are uploaded,
in the same job, and never regenerated from a checkout afterwards.

## 3. The GitHub ruleset for `dovetail--v*` tags

`.github/rulesets/dovetail-release-tags.json` is the ruleset as a reviewable
file. **GitHub imports that file; it never reads it from this repository.** The
two stay in step only while somebody re-imports after a change, and nothing in
CI can detect divergence — `scripts/test-release-publish.sh` checks the file's
own bytes against this pack's name, which proves the document is self-consistent
and proves nothing about the live setting.

Required rules, all four:

| rule | closes |
|---|---|
| `creation` | a tag cut by anything other than the publishing identity |
| `update` | a published tag repointed at another commit |
| `deletion` | a published tag removed and re-cut |
| `non_fast_forward` | a tag moved *backwards* without ever being deleted |

`non_fast_forward` is the one most easily dropped as redundant. It is not:
`update` and `deletion` are the routes people think of, and moving a ref to an
earlier commit is the route that leaves the tag looking untouched. As of this
commit `scripts/test-release-publish.sh` requires all four; before it, it
required three, and the fourth could have been deleted from the file with CI
staying green.

**`bypass_actors` ships empty, and that fails closed.** Until the publishing
identity is added there, importing this ruleset makes releases impossible rather
than exclusive — including releases cut by `release-publish.yml`. Import and
then add the actor; do not add a placeholder with `actor_id: 0`, which reads as
configured and grants nothing.

**`required_signatures` is deliberately absent.** GitHub's tag rulesets offer
it, and adding it today would break the only sanctioned publish route, because
`gh api POST /git/tags` cannot produce a signature. It is the last step of § 1,
not the first — adding it before signing works converts a documented gap into an
outage.

**Importing is a manual step and cannot be automated from here.** Settings →
Rules → Rulesets → New ruleset → Import a ruleset, then select the JSON. Re-import
after any change to the file, and record when you did.

## 4. Branch protection is not tag protection

They are different targets with different failure modes, and a repository can
have either without the other.

| | protects | against | where configured |
|---|---|---|---|
| branch protection | `main` | merging work the checks did not run on | repository settings; see `AGENTS.md` "The branch protecting the gate" |
| tag ruleset | `refs/tags/dovetail--v*` | a release tag nobody's gate produced | repository settings; file at `.github/rulesets/` |

Branch protection on `main` says nothing about tags: a tag is a pointer and can
be pushed by hand at any commit, protected branch or not. Tag protection says
nothing about `main`: a ruleset over `refs/tags/` does not care what merged.
Configuring one and assuming the other is covered is the specific mistake this
section exists to name.

The one place they meet is the `release` environment's deployment-branch rule,
which restricts *which ref may dispatch a publish* to `main` — a branch-side
control that guards a tag-side action. It is described in `AGENTS.md` under the
environment secret, and it is settings-side like the rest.

## 5. The publishing identity and its minimum permissions

`AGENTS.md` covers why the identity should be a GitHub App and why the key is an
environment secret rather than a repository secret. What belongs here is the
permission floor, as a thing to check against rather than to reason out again:

| workflow / job | permissions | why not less, why not more |
|---|---|---|
| `checks.yml` | `contents: read` | checkout only; it publishes nothing |
| `release.yml` | `contents: read`, `actions: read` | it audits a tag after the fact; `actions: read` is the Actions API query for whether `checks` passed |
| `release-publish.yml` (workflow) | `{}` | every scope granted per job, so the default is nothing |
| `release-publish.yml` → `validate` | `contents: read`, `actions: read` | runs the gate in the mode that cannot write |
| `release-publish.yml` → `publish` | `contents: write`, `actions: read` | the tag object, the ref and the release object; nothing else |

Two properties are load-bearing and are asserted by
`scripts/test-release-publish.sh` on every push and pull request: exactly one job
may write, and it waits on a job that cannot. A permission granted for the last
step of a run is granted for all of it, so keeping the read-only answer in a job
that never held the write is what makes "it passed" separable from "it
published".

Signing (§ 1) changes this table. Creating the tag locally with `git tag -s` and
pushing it still needs only `contents: write`; reading the signing key needs the
environment, not a broader token. If a proposed signing design asks for
`id-token: write` or any scope beyond `contents`, that is the signal to check
whether it is doing something other than signing a tag.

## Verifying a release you received

The whole procedure, for somebody who is not the publisher:

```bash
git clone https://github.com/OpenCnid/dovetail.git
cd dovetail
git fetch --tags origin
bash scripts/verify-release.sh --strict dovetail--v0.4.1
```

`--strict` is right here: a consumer wants a single non-zero for "this is not
established", and does not care whether the reason was a real negative or an
unreadable one. Drop it to see the difference.

## What this cannot establish

Said here rather than found later.

- **Whether the ruleset is actually active on GitHub.** Nothing in a repository
  can read its own settings. The file is a reviewable record of intent; treat a
  green CI run as evidence about the file and about nothing else.
- **Whether the signing key belongs to whoever may publish.** A verified
  signature names a key. Binding that key to an identity is what
  `allowed_signers` is for, and until § 1 step 2 lands there is nothing to bind
  against.
- **What `main` ships to everyone else.** `AGENTS.md` records that the install
  route the README documents resolves the default branch and consults no tag, so
  every guarantee above governs the routes that *do* resolve tags — a dependency
  range against `dovetail--v*`, or a source pinned with `#ref`. A consumer on
  the documented route receives `main`'s tip, and none of this describes it.
- **That an SBOM's contents are true.** `scripts/verify-release.sh` reports that
  such a document is present. Reading one and judging its claims is a different
  tool, and saying otherwise here would be the overclaim the rest of this
  document is written against.

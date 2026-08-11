# Reference material

The records this skill cites, mirrored **byte-for-byte** from the originating
repository so the skill travels intact: lift this skill's directory out of the
repo and every document it cites comes with it. That repository is deprecated —
these copies are what remain, and they are what the skill's claims resolve
against.

## How to read these

Pull the cited section; leave the rest on disk. Several of these run past 40 KB,
and loading one whole spends the context the skill exists to spend well.

```
Grep "{Section_Number_Or_Exact_Heading}" references/{Mirrored_File} -A 40
```

The skill body names the section it wants at each step. That name is the read
instruction — follow it to the section, not to the file.

## These are mirrors, and they are now the record

*Corrected 2026-08-01.* This section previously said the canonical copy was the
source path in the table below, and that on any divergence **the record wins and
the mirror is replaced from source**. **That is inverted.** The originating
repository is deprecated and will be archived or deleted; it cannot adjudicate a
divergence it will not be present for, and a mirror that defers to an absent
authority has no way to settle a reading at all.

**These mirrors are canonical.** They were verified byte-for-byte against the
source at the recorded commit, so what is canonical here is what was canonical
there — the authority moved, the bytes did not.

A mirror is still never edited in place. Byte-identity to the source at the
recorded commit is what made it checkable, and editing one destroys the only
property that justified copying it rather than restating it.

Nothing is appended inside the mirrored files. Byte-identity to the source is
what makes a mirror checkable, and a provenance header written into the file
would be the first thing to destroy it — so provenance lives here instead.

No sync check is installed, and none is possible once the originating repository
is archived. These are portability snapshots taken at one commit; the hashes
below are what a reader verifies a mirror against, with or without that
repository present.

## Provenance

Mirrored from the Trellis repository at commit `65fdb1f`, dated 2026-07-25.

| File | Canonical source | Bytes | SHA-256 |
|---|---|---|---|
| `AMBIENT.md` | `AMBIENT.md` | 8,070 | `dfb614b83b3eb4ba22fb6a33d12e445bbb9ead5c5e1e1a6a51b50d1febf33603` |
| `COMPOSITION_FROM_PRIMITIVES.md` | `docs/architecture/COMPOSITION_FROM_PRIMITIVES.md` | 13,782 | `9b69b44db0e5e02d824a836452d6e031ad10c4d3b8c3f0cedd0f703e595d73b0` |
| `DOUBTS_WORKSPACE.md` | `docs/architecture/DOUBTS_WORKSPACE.md` | 37,859 | `aec7483652bc6f369f003674c8f3491df5136fd38e0dd98605531397c2663bda` |
| `FOUR_JUDGE_BASIC_MODEL.md` | `docs/product/epistemic-support/FOUR_JUDGE_BASIC_MODEL.md` | 9,467 | `986bd635870533ef6c62c4fb48f0d53bf5f0bd26e236dd7f40c7add226b7b8b8` |
| `FOUR_JUDGE_DESIGN.md` | `docs/product/epistemic-support/FOUR_JUDGE_DESIGN.md` | 20,170 | `c944586e345668cc93a75faa431a0632e23484b5a705fa5991dd693fbb344fa0` |
| `JUDGE_COMPOSITION_CEREMONY.md` | `docs/product/epistemic-support/JUDGE_COMPOSITION_CEREMONY.md` | 14,828 | `f5a54786d014222992687ab6b51f983e37af4226afdf7c26501ee04d3037e3c1` |
| `JUDGE_COMPOSITION_GAME.md` | `docs/product/epistemic-support/JUDGE_COMPOSITION_GAME.md` | 29,004 | `0e3ef78b8ffd9f0c62b022b7a9db10515873e18550d02cc412971587dfe34574` |
| `JUDGE_CONVOCATION_DESIGN.md` | `docs/product/epistemic-support/JUDGE_CONVOCATION_DESIGN.md` | 52,623 | `e078f60d63ed738f5b789377f136a4141359b2a87198e5bd4e63d998dd43230b` |
| `JUDGE_INTAKE_DESIGN.md` | `docs/product/epistemic-support/JUDGE_INTAKE_DESIGN.md` | 24,436 | `b6fd8adbcdcac56d4d2d57f063011f26cd85b5f2ef7242bb7ed5a1f946622a46` |
| `PROGRAM_CONTEXT.md` | `docs/product/epistemic-support/PROGRAM_CONTEXT.md` | 25,401 | `e240ce3f6cb06df6bd577ecb1714c6fd612cbf049b0d705266c1da68644f593b` |
| `RECONCILIATION.md` | `docs/product/epistemic-support/RECONCILIATION.md` | 46,647 | `a88c9539e88033825a2f65b70a4634c4cf0dd1d4c2e4966fc9021234f298e14d` |
| `STANDING_MODEL.md` | `docs/product/epistemic-support/STANDING_MODEL.md` | 8,825 | `484fc3c860e834a8afaed6dff6741c585ec3464c7466b09ad3d8421932904cfd` |

**A caution on the byte counts and digests above.** They were recorded against a
CRLF working copy. The files as committed here are LF-normalised by
`.gitattributes`, so `wc -c` on a fresh checkout reports fewer bytes (for
`DOUBTS_WORKSPACE.md`: 37,176 rather than 37,859 — a difference of exactly its
683 lines) and the SHA-256 values will not match either. Read that column as the
snapshot's own fingerprint rather than as a cross-platform constant.

### Verified blob SHAs — added 2026-08-01

**The SHA-256 column above could not be checked without a Trellis checkout, which
made it useless for exactly the situation this directory exists for.** Every
mirror was therefore re-verified against the source by **git blob SHA**, which is
computed over the normalised content and so is identical on a CRLF checkout and
an LF one. These are the values a reader checks against, and they need nothing
outside this repository.

| File | Blob SHA (verified against source at `65fdb1f`) |
|---|---|
| `AMBIENT.md` | `108967e9602d2a8820e3712787b80a02e76f73c3` |
| `COMPOSITION_FROM_PRIMITIVES.md` | `3d95cd1e6d1a2bc425da8f1c17daa10ba8c3e65c` |
| `DOUBTS_WORKSPACE.md` | `083aa8d5f3d383a34205e8f4c83cb2c1c97fd2b7` |
| `FOUR_JUDGE_BASIC_MODEL.md` | `2cf8569cacb2197c60a7db48ad3aea2b1a2f4858` |
| `FOUR_JUDGE_DESIGN.md` | `6b0a2003d3223b18f7f3f41e65d4ba2aeaaa5b87` |
| `JUDGE_COMPOSITION_CEREMONY.md` | `a8510c331061580af38ac583cb451e6535af6888` |
| `JUDGE_COMPOSITION_GAME.md` | `3d64ecde2adb7a7dcac0b0213a3c6eccc6cf0be0` |
| `JUDGE_CONVOCATION_DESIGN.md` | `0f7cf0aa6f2acd65719b06ce060b69f7678f129a` |
| `JUDGE_INTAKE_DESIGN.md` | `afc2d4c30b785c2bcf662977d4e13246418c0925` |
| `PROGRAM_CONTEXT.md` | `84a6bf4ab29c687483b0d92d3c762170b83a9f58` |
| `RECONCILIATION.md` | `ca8b605f2b92ecc8468d3446c589a1312bc288ad` |
| `STANDING_MODEL.md` | `bc0eb064538f23c9f33550aec1d4980d251ed632` |

`DOUBTS_WORKSPACE.md` carries the same blob SHA in the `self-play` skill, which
mirrors it from the same content at a different commit. Two skills arriving at
one hash for one record is the property this column exists to make visible.

### Added 2026-08-01

Mirrored from the originating repository at commit `07bd744`, verified by **git
blob SHA** against the source rather than by having been copied:

| File | Canonical source | Bytes | Blob SHA (verified) |
|---|---|---|---|
| `judge_panel.ts` | `src/core/graph/judge_panel.ts` | 22,659 | `faf4f19ea1deafdf12db778a4389d99878da0540` |

Its working-copy SHA-256 is
`926388b10416eb7e3369e01b67d77d70a6bcd12da3372a263c124044ea7eab3d`, subject to
the same line-ending caution as above.

**Authored here, not mirrored** — these carry no byte-identity claim and are this
repository's own work:

| File | What it is |
|---|---|
| `registry-parameters.md` | What the four registries are, why no enumeration was ever written, and the fourteen-parameter working set recovered from `judge_panel.ts`. Read it as a record, never as a roster. |
| `thesis-and-provenance.md` | Distillation, reconciliation, the adopted thesis and its standing falsifier, and the authority correction in full. Moved out of `SKILL.md`. |
| `failure-modes.md` | The seven failure modes at full length, plus § *Range*. Moved out of `SKILL.md`. |
| `standing-model-reframing.md` | The July 20 standing-model pointer at full length. Moved out of `SKILL.md`. |
| `substrate-and-cases.md` | The two substrate-conditional notes and the worked ground-block case. Moved out of `SKILL.md`. |

The four "moved out of `SKILL.md`" files were relocated on 2026-08-01 to bring the
body under the ~19,900-character surviving prefix. **Nothing was deleted** — every
one of those sections already sat past the cut, so in any compacted session they
were gone. `references/` is never truncated.

### A fourteenth mirror lives outside this directory

[`docs/origin-readme.md`](../../../docs/judge-composition/docs/origin-readme.md) is also a
byte-for-byte mirror — of `.claude/skills/judge-composition/README.md` at
`65fdb1f`, blob `573dc53f4f97c539b8aa76b94978c02fef940efe`, verified the same
way. It shipped with the first publish of this repository and went unrecorded
here until 2026-08-01.

It is listed now because an unregistered mirror is the worst of both kinds: it
carries byte-identity that nobody knows to preserve, and it reads as this
repository's own prose when it is not. **It is a historical artifact, and two
things in it are superseded** — see [`docs/README.md`](../../../docs/judge-composition/docs/README.md),
which states the correction without touching the mirrored bytes.

## Verifying a mirror

Check any mirror from inside this repository, with nothing else installed:

```
git hash-object references/{Mirrored_File}
```

Equal to its recorded blob SHA, or it is not the record. This works on any
platform and with the originating repository gone, which is the whole reason the
blob-SHA column was added.

*Corrected 2026-08-01.* This section previously told a reader to run `sha256sum`
across `references/{Mirrored_File}` and the matching path in **a checked-out
Trellis repository**. That instruction was sound only while that repository could
be checked out, and it is the one instruction here that had to survive its
removal. It is replaced rather than deleted so the earlier method is legible: it
compared two working files so both got one checkout's line-ending treatment. The
blob SHA gets the same property without needing the second file at all.

# What is in `docs/`, and what is superseded in it

## `origin-readme.md` is a mirror, not this repository's prose

It is a byte-for-byte copy of `.claude/skills/judge-composition/README.md` as it
stood in the originating repository at commit `65fdb1f` — blob
`573dc53f4f97c539b8aa76b94978c02fef940efe`, verified by hash rather than by
having been copied. It is kept because it is the record of why this skill was
versioned in-repo at all, and of the Session 71 failure that produced that
decision. That history is not written down anywhere else.

**It is not edited, and the corrections below are written here instead.** Its
value is that it says what the origin said, unaltered; a repair applied inside it
would leave a document that is neither the origin's record nor honestly this
repository's own. Verify it the same way as any mirror:

```
git hash-object docs/origin-readme.md
```

## Two things in it are superseded

Read it with both of these in hand.

### 1. Its drift rule is inverted

Its § *The drift rule governs, and it points one way* states that
`JUDGE_COMPOSITION_GAME.md` §11 is **canonical over this skill**, that on any
drift *the record wins and the skill is corrected — never the reverse*, and that
this directory *is not an independent authority*.

**That is now inverted, and the reason is not that the rule was unsound.** It was
correct while the record lived in a maintained repository that could adjudicate a
divergence. That repository is deprecated and will be archived or deleted. An
authority that will not be present cannot settle anything, and a document that
defers to it has no way to resolve a reading at all.

**This repository is canonical for this skill and for the records mirrored in
`skills/judge-composition/references/`** — including
`JUDGE_COMPOSITION_GAME.md` itself, which ships there byte-for-byte at the commit
it was verified against. What was canonical there is what is canonical here. The
authority moved; the bytes did not.

The rule's *substance* survives the inversion intact: a paraphrase is still drift
rather than an implementation, the twenty rules of §6 are still cited by number
rather than restated, and the mirrored record still governs the skill body. Only
the location of the record changed.

### 2. Its links do not resolve here

It uses relative paths written for the originating repository's layout — for
instance `../../../docs/product/epistemic-support/JUDGE_COMPOSITION_GAME.md`.
Those resolve to nothing in this repository and would 404 against the origin once
it is archived.

Every document it names by filename is mirrored in
[`skills/judge-composition/references/`](../skills/judge-composition/references/).
**Read the filename, ignore the path**: `JUDGE_COMPOSITION_GAME.md`,
`PROGRAM_CONTEXT.md`, `COMPOSITION_FROM_PRIMITIVES.md`,
`JUDGE_COMPOSITION_CEREMONY.md` and `STANDING_MODEL.md` are all there, with their
verified blob SHAs recorded in that directory's
[`README.md`](../skills/judge-composition/references/README.md).

## What is not superseded

Its § *What is invariant, and what is not* and its § *Why it is versioned here*
stand unchanged, and the no-default-cast ruling it records is still binding. The
four roles are invariant; the judges filling them are composed per context. That
is the skill's central claim and this document is part of its provenance.

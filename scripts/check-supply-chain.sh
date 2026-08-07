#!/usr/bin/env bash
# What this asks, and why it is not one of the release-gate scripts.
#
# `test-release-check.sh` asks whether the gate grades the commit it says it
# grades. `test-release-publish.sh` asks whether there is a route to a tag that
# does not wait for it. Both are questions about *this* repository's own code.
# This one is about the code this repository runs that it did not write, and
# about the code it asks a package index for -- a third question, which fails
# for third reasons, so it is checked apart.
#
# Two layers:
#
#   actions      every `uses:` in every workflow names a commit, and says which
#                release that commit was. A major tag is not a version, it is a
#                pointer somebody else force-moves: `actions/checkout` ships an
#                `update-main-version.yml` whose last step is `git push origin
#                ${major} --force`, and upstream's `v6` sits eleven commits past
#                `v6.0.0` as a result. So `@v7` says "whatever that tag points
#                at when the runner resolves it", and a green check on Monday is
#                not evidence about Tuesday's run. The comment is half the pin
#                and is required too: a bare SHA is a fact nobody can re-check
#                without cloning the upstream repository and bisecting it, and
#                the whole point of pinning is that the pin can be audited.
#
#   python       every distribution this repository installs is named in a
#                requirements file, with a lower bound. Naming a package on a
#                pip command line instead puts a dependency somewhere no policy
#                check will look, which is how `pytest` came to be installed on
#                every run, at whatever version was newest that morning, for as
#                long as nobody read the pip line in `checks.yml`.
#
#                A lower bound, and deliberately not an upper one. The only
#                requirements file here ships to users — `install.sh` copies the
#                skill directory into `~/.claude/skills/` — so a ceiling would
#                narrow what a user's machine may already satisfy in order to
#                buy CI a property CI can have another way. The bound that keeps
#                a known-bad release out is the floor; the ceiling mostly buys
#                the illusion of one, since it excludes no release that exists.
#
#                Which files count is the part this check gets wrong if it is
#                careless, so it does not guess from a filename. It scans what
#                the workflows actually install from, follows `-r` includes out
#                of those files, and *then* adds anything tracked that looks
#                like a requirements file. Selecting on the name alone would
#                have let a `dev-requirements.txt` — or a `requirements/dev.txt`
#                — carry an unbounded pin under a green tick, which is worse
#                than no check, because the status quo at least fails honestly
#                with the package visible on the pip line.
#
# What this cannot do, said here rather than found later. It reads the ref
# written in the file; it cannot tell you that ref is a commit anybody reviewed,
# or that the upstream repository still exists. Pinning moves the trust from
# "the tag owner will not repoint this" to "the commit named here was read
# once", and only the second is a thing this repository can hold itself to.
# Nothing here reaches the network, deliberately: a check that fails when
# api.github.com is slow is a check people learn to re-run rather than read.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Selected by capability rather than by name: a box can easily carry a `python3`
# without PyYAML beside a `python` that has it, and the actions layer parses YAML
# rather than grepping it -- a `uses:` is a mapping value, and which mappings are
# steps is a question about the document, not about the line.
PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import yaml' >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done

fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }

# ----------------------------------------------------------------- actions
scan_action_refs() {
  "$PY" - <<'PY'
import pathlib, re, sys, yaml

# A reference this repository is responsible for pinning. `./path` is an action
# committed here, already as immutable as the commit reading it; a `docker://`
# reference carries a digest in its own syntax and is checked for one below.
THIRD_PARTY = re.compile(r"^[^./][^@]*@(?P<ref>.+)$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")

# The same line as the parser sees it, so the trailing comment -- which YAML
# discards and which is the half of the pin a human re-checks -- can be read.
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<ref>\S+)(?P<rest>.*)$")


def uses_values(node, path="$"):
    """Every `uses:` string in the document, with the path that reaches it."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                yield path, value
            else:
                yield from uses_values(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from uses_values(value, f"{path}[{index}]")


workflows = sorted(
    p for ext in ("*.yml", "*.yaml")
    for p in pathlib.Path(".github/workflows").glob(ext)
)
if not workflows:
    sys.exit("  no workflows found — the selection is wrong, not the repository")

findings = []
for workflow in workflows:
    where = workflow.as_posix()
    text = workflow.read_text(encoding="utf-8")
    document = yaml.safe_load(text)

    # Read from the text so the comment survives, and keyed by the ref so the
    # two readings can be compared rather than trusted separately.
    # Accumulated rather than assigned: one action can be used by several jobs
    # in a file -- `release-publish.yml` checks out twice -- and an assignment
    # would let a commented line further down stand in for a bare one above it.
    commented = {}
    for line in text.splitlines():
        match = USES_LINE.match(line)
        if match:
            ref = match.group("ref")
            has_comment = "#" in match.group("rest")
            commented[ref] = commented.get(ref, True) and has_comment

    structural = list(uses_values(document))
    for path, ref in structural:
        if ref.startswith("docker://"):
            if "@sha256:" not in ref:
                findings.append((where, path, ref, "a container reference without a digest"))
            continue
        match = THIRD_PARTY.match(ref)
        if not match:
            # `./something` — this repository's own file, pinned by being here.
            continue
        if not COMMIT.fullmatch(match.group("ref")):
            findings.append((where, path, ref, "a moving ref, not a commit SHA"))
        elif not commented.get(ref, False):
            findings.append((where, path, ref, "a commit SHA with no comment naming the release"))

    # A `uses:` the line reader could not see is a `uses:` whose comment nobody
    # checked, so the disagreement is the finding rather than a reason to guess.
    if len(commented) < len({ref for _, ref in structural}):
        findings.append((where, "$", "", "a `uses:` the line reader could not match — the comment check did not cover it"))

for workflow in workflows:
    where = workflow.as_posix()
    hits = [f for f in findings if f[0] == where]
    if hits:
        print(f"  {'FAIL':<6} {where}")
        for _, path, ref, why in hits:
            print(f"         {path} uses {ref or '(unreadable)'}")
            print(f"         {why}")
            print("         Pin it to the 40-character commit the release resolves to,")
            print("         with a trailing `# <release>` so the pin can be re-checked.")
    else:
        print(f"  {'ok':<6} {where}")

sys.exit(1 if findings else 0)
PY
}

# ------------------------------------------------------------------ python
scan_python_requirements() {
  "$PY" - <<'PY'
import pathlib, re, subprocess, sys, yaml

# A requirement line, split into the distribution and everything after it. The
# markers and extras this repository does not use are still parsed rather than
# refused, so the check fails on an unbounded pin and not on valid syntax.
REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>.*)$")

INCLUDE = re.compile(r"^\s*(?:-r|--requirement|-c|--constraint)[=\s]+(?P<target>\S+)")

workflows = sorted(
    p for ext in ("*.yml", "*.yaml")
    for p in pathlib.Path(".github/workflows").glob(ext)
)
if not workflows:
    sys.exit("  no workflows found — the selection is wrong, not the repository")


def run_bodies(node):
    """Every `run:` string in the document."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "run" and isinstance(value, str):
                yield value
            else:
                yield from run_bodies(value)
    elif isinstance(node, list):
        for value in node:
            yield from run_bodies(value)


def commands(body):
    """`pip install` invocations, one logical shell command each.

    Line-by-line with backslash continuations joined, rather than one regex
    swallowing every indented line after the match: a `pip install` inside an
    `if` -- the shape this repository already uses for apt-get -- would
    otherwise make the rest of the block read as arguments to pip.
    """
    joined, buffer = [], ""
    for raw in body.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            buffer += line[:-1] + " "
            continue
        joined.append(buffer + line)
        buffer = ""
    if buffer:
        joined.append(buffer)
    for line in joined:
        for piece in re.split(r"&&|\|\||[;|]", line):
            match = re.search(r"\bpip\s+install\b(?P<args>.*)$", piece)
            if match:
                yield match.group("args")


findings = []

# Which files count is decided by what the workflows install from, not by what
# a file is called. Selecting on the name lets a `dev-requirements.txt` or a
# `requirements/dev.txt` carry an unbounded pin past a green check -- the
# failure this layer exists to prevent, wearing the check's own approval.
files, pending = [], []
for workflow in workflows:
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for body in run_bodies(document):
        for args in commands(body):
            tokens = args.split()
            for index, token in enumerate(tokens):
                if token in ("-r", "--requirement", "-c", "--constraint") and index + 1 < len(tokens):
                    pending.append((workflow.as_posix(), tokens[index + 1]))

for where, target in pending:
    path = pathlib.Path(target)
    if not path.is_file():
        findings.append((where, 0, target, "installed from a requirements file that is not in the repository"))

# Follow `-r` out of the files themselves, so a file reached only by an include
# is scanned rather than trusted, then add anything tracked that looks like one.
seen, queue = set(), [pathlib.Path(t) for _, t in pending if pathlib.Path(t).is_file()]
tracked = subprocess.run(
    ["git", "ls-files"], capture_output=True, text=True, check=True,
).stdout.splitlines()
queue += [
    pathlib.Path(p) for p in tracked
    if "requirements" in pathlib.PurePosixPath(p).name and p.endswith(".txt")
]
while queue:
    path = queue.pop()
    key = path.as_posix()
    if key in seen or not path.is_file():
        continue
    seen.add(key)
    files.append(path)
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = INCLUDE.match(raw)
        if match:
            queue.append((path.parent / match.group("target")).resolve().relative_to(pathlib.Path.cwd().resolve()))

files.sort()
if not files:
    sys.exit("  no requirements files found — the selection is wrong, not the repository")
for path in files:
    where = path.as_posix()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-"):
            # `-r other.txt` and friends: an include, not a distribution.
            continue
        match = REQUIREMENT.match(line)
        if not match:
            findings.append((where, number, line, "not a requirement this check can read"))
            continue
        spec = match.group("spec").split(";", 1)[0]
        if "==" in spec:
            continue  # an exact pin is already both bounds.
        if "~=" in spec:
            continue  # `~=1.2.3` is `>=1.2.3` and `==1.2.*` written once.
        if ">" not in spec:  # covers `>` and `>=`
            findings.append((where, number, line, "no lower bound -- a known-bad release satisfies it"))

# The other half: a dependency named on a pip command line is a dependency no
# requirements file declares, so no floor above applies to it.
SKIP = {"pip", "install", "python", "-m", "--user", "--upgrade", "--quiet", "-q",
        "--disable-pip-version-check", "--no-deps", "--require-hashes"}

for workflow in workflows:
    where = workflow.as_posix()
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for body in run_bodies(document):
        for args in commands(body):
            tokens = args.split()
            index = 0
            while index < len(tokens):
                token = tokens[index]
                if token in ("-r", "--requirement", "-c", "--constraint"):
                    index += 2
                    continue
                if token.startswith("-") or token in SKIP:
                    index += 1
                    continue
                findings.append((where, 0, token, "installed by name on a pip line -- declare it in a requirements file"))
                index += 1

if findings:
    for where, number, subject, why in findings:
        location = f"{where}:{number}" if number else where
        print(f"  {'FAIL':<6} {location}")
        print(f"         {subject}")
        print(f"         {why}")
else:
    for path in files:
        print(f"  {'ok':<6} {path.as_posix()}")
    print(f"  {'ok':<6} no workflow installs a distribution by name")

sys.exit(1 if findings else 0)
PY
}

echo "actions — every uses: names a commit, and says which release"

if [ -z "$PY" ]; then
  note FAIL "no python with PyYAML — the workflows were not parsed"
  echo "         Install it (python -m pip install pyyaml) rather than skipping:"
  echo "         an unparsed workflow is an unpinned workflow nobody was told about."
  fail=1
else
  scan_action_refs || fail=1

  echo
  echo "python — every distribution is declared, with a floor"
  scan_python_requirements || fail=1
fi

echo
[ "$fail" -eq 0 ] && echo "Supply-chain checks passed." || echo "Supply-chain checks FAILED."
exit "$fail"

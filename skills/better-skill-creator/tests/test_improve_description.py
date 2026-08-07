#!/usr/bin/env python3
"""Tests for scripts/improve_description.py.

Run from the skill root:

    python -m unittest tests.test_improve_description -v

This is the component that **rewrites the user's description** -- the output
they actually adopt -- and it shipped with no test file at all while its
siblings sat at 84-96%. Verification called that out as the highest-blast-radius
gap in the tree (research/V7-verification.md B, _REMEDIATION.md R2).

Nothing here spends money. `improve_description._call_claude` launches whatever
`BETTER_SKILL_CREATOR_CLAUDE_ARGV` names; these tests point it at
tests/fixtures/stub_claude.py in its optimizer mode, which records the prompt it
was handed to `STUB_CLAUDE_PROMPT_LOG`. That is the point: the assertions are
about **what the optimizer was shown and what came back**, not about how the
prompt string was assembled.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.improve_description import improve_description  # noqa: E402
from scripts.run_eval import (  # noqa: E402
    INHERIT_PERMISSION_MODE,
    SAFE_PERMISSION_MODE,
    PermissionModeError,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STUB = FIXTURES / "stub_claude.py"

SKILL_CONTENT = "# Widget forge\n\nAuthors widget.toml manifests.\n"
CURRENT = "Use this skill when a widget manifest needs authoring."


def tagged(text: str) -> str:
    return f"<new_description>{text}</new_description>"


class OptimizerHarness(unittest.TestCase):
    """Wires improve_description's `claude -p` call to the stub."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="improve-desc-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.control_path = self.tmp / "control.json"
        self.prompt_log = self.tmp / "prompts.jsonl"

        self._saved_env = {
            k: os.environ.get(k)
            for k in ("BETTER_SKILL_CREATOR_CLAUDE_ARGV", "STUB_CLAUDE_CONTROL",
                      "STUB_CLAUDE_PROMPT_LOG", "STUB_CLAUDE_REPORT")
        }
        os.environ["BETTER_SKILL_CREATOR_CLAUDE_ARGV"] = json.dumps([sys.executable, str(STUB)])
        os.environ["STUB_CLAUDE_CONTROL"] = str(self.control_path)
        os.environ["STUB_CLAUDE_PROMPT_LOG"] = str(self.prompt_log)
        os.environ.pop("STUB_CLAUDE_REPORT", None)
        self.addCleanup(self._restore_env)
        self.control()

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def control(self, **kwargs):
        self.control_path.write_text(json.dumps(kwargs), encoding="utf-8")

    def prompts(self) -> list[dict]:
        if not self.prompt_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.prompt_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def improve(self, eval_results, *, history=None, model="haiku", **kwargs):
        return improve_description(
            skill_name="widget-forge",
            skill_content=SKILL_CONTENT,
            current_description=CURRENT,
            eval_results=eval_results,
            history=history if history is not None else [],
            model=model,
            **kwargs,
        )


def row(query, should_trigger, passed, triggers=0, runs=3, errored=0):
    return {
        "query": query,
        "should_trigger": should_trigger,
        "pass": passed,
        "triggers": triggers,
        "runs": runs,
        "errored": errored,
    }


def results(rows):
    passed = sum(1 for r in rows if r["pass"] is True)
    failed = sum(1 for r in rows if r["pass"] is False)
    return {
        "results": rows,
        "summary": {"passed": passed, "failed": failed, "total": len(rows)},
    }


class TestErrorRowsAreWithheld(OptimizerHarness):
    """C8/C4: a query whose every probe errored is not evidence about the
    description. It is neither a failure to fix nor a false trigger to suppress,
    so it must not reach the optimizer as either -- an optimizer that "fixes" a
    dead probe rewrites a description that was never measured."""

    def _mixed(self):
        return results([
            row("author a widget manifest", True, False, triggers=0),
            row("what is the capital of France", False, False, triggers=3),
            row("UNMEASURED harness died here", True, None, triggers=0, runs=0, errored=3),
            row("draft a widget.toml", True, True, triggers=3),
        ])

    def test_errored_query_text_never_reaches_the_optimizer(self):
        self.improve(self._mixed())
        prompt = self.prompts()[0]["prompt"]
        self.assertNotIn("UNMEASURED", prompt)

    def test_genuine_failures_do_reach_the_optimizer(self):
        self.improve(self._mixed())
        prompt = self.prompts()[0]["prompt"]
        self.assertIn("author a widget manifest", prompt)
        self.assertIn("what is the capital of France", prompt)

    def test_the_unmeasured_count_is_disclosed_rather_than_hidden(self):
        """Withholding the rows is right; pretending they did not happen is not.
        The optimizer is told how much of the set it is not seeing."""
        self.improve(self._mixed())
        prompt = self.prompts()[0]["prompt"]
        self.assertIn("could not be measured at all", prompt)
        self.assertIn("not evidence about the", prompt)

    def test_no_note_when_everything_was_measured(self):
        self.improve(results([
            row("author a widget manifest", True, False),
            row("capital of France", False, True),
        ]))
        self.assertNotIn("could not be measured at all", self.prompts()[0]["prompt"])

    def test_errored_rows_in_history_are_not_replayed_as_results(self):
        history = [{
            "description": "an earlier attempt",
            "train_passed": 1,
            "train_total": 3,
            "results": [
                row("kept row", True, True, triggers=3),
                row("HISTORIC UNMEASURED", True, None, runs=0, errored=3),
            ],
        }]
        self.improve(results([row("author a widget manifest", True, False)]), history=history)
        prompt = self.prompts()[0]["prompt"]
        self.assertIn("kept row", prompt)
        self.assertNotIn("HISTORIC UNMEASURED", prompt)

    def test_a_history_note_is_carried_into_the_prompt(self):
        """A failed optimizer call leaves a note on the iteration it broke. The
        next attempt should see why the previous one produced nothing."""
        history = [{
            "description": "an earlier attempt", "train_passed": 1, "train_total": 3,
            "results": [], "note": "improve_description failed: RuntimeError: rate limited",
        }]
        self.improve(results([row("q", True, False)]), history=history)
        self.assertIn("rate limited", self.prompts()[0]["prompt"])

    def test_a_history_entry_without_results_still_renders(self):
        history = [{"description": "an earlier attempt", "passed": 1, "total": 3}]
        self.improve(results([row("q", True, False)]), history=history)
        prompt = self.prompts()[0]["prompt"]
        self.assertIn("an earlier attempt", prompt)
        self.assertIn("train=1/3", prompt)

    def test_held_out_scores_appear_only_when_a_caller_asks_for_them(self):
        """`test_results` is the un-blinding hatch. run_loop never passes it --
        selection is by held-out score, so an optimizer that can see those rows
        can tune against them. Pinned here so the default stays blind."""
        payload = results([row("q", True, False)])
        held = results([row("h", True, True)])
        self.assertNotIn("Test:", self.prompts_after(payload))
        self.improve(payload, test_results=held)
        self.assertIn("Test: 1/1", self.prompts()[-1]["prompt"])

    def prompts_after(self, payload):
        self.improve(payload)
        return self.prompts()[-1]["prompt"]

    def test_previous_attempts_are_shown_so_they_are_not_repeated(self):
        history = [{"description": "a distinctive earlier attempt", "train_passed": 1,
                    "train_total": 3, "results": []}]
        self.improve(results([row("q", True, False)]), history=history)
        prompt = self.prompts()[0]["prompt"]
        self.assertIn("a distinctive earlier attempt", prompt)
        self.assertIn("do NOT repeat", prompt)


class TestRewriteNet(OptimizerHarness):
    """The 1024-character cap is not a truncation. A description over it fails
    frontmatter validation and the skill does not load at all, which the user
    experiences as "it never triggers"."""

    def test_an_over_long_answer_is_sent_back_for_a_rewrite(self):
        long_text = "L" * 1100
        self.control(optimizer_responses=[tagged(long_text), tagged("S" * 200)])
        out = self.improve(results([row("q", True, False)]))
        self.assertEqual(out, "S" * 200)
        self.assertEqual(len(self.prompts()), 2, "the net must make a second call")

    def test_the_rewrite_prompt_quotes_the_overrun_and_its_length(self):
        long_text = "L" * 1100
        self.control(optimizer_responses=[tagged(long_text), tagged("S" * 200)])
        self.improve(results([row("q", True, False)]))
        second = self.prompts()[1]["prompt"]
        self.assertIn("1024-character hard limit", second)
        self.assertIn("1100 characters", second)
        self.assertIn(long_text, second)

    def test_an_answer_at_the_limit_is_accepted_unchanged(self):
        exact = "E" * 1024
        self.control(optimizer_responses=[tagged(exact)])
        out = self.improve(results([row("q", True, False)]))
        self.assertEqual(len(out), 1024)
        self.assertEqual(len(self.prompts()), 1, "1024 is inside the limit, not over it")

    def test_one_character_over_the_limit_triggers_the_net(self):
        self.control(optimizer_responses=[tagged("E" * 1025), tagged("short")])
        self.improve(results([row("q", True, False)]))
        self.assertEqual(len(self.prompts()), 2)

    def test_a_rewrite_that_is_still_too_long_is_refused_not_returned(self):
        """Both calls came back over the cap. Returning the second would let the
        loop measure, score and recommend a description that cannot load."""
        self.control(optimizer_responses=[tagged("L" * 1100), tagged("M" * 1090)])
        with self.assertRaises(RuntimeError) as ctx:
            self.improve(results([row("q", True, False)]))
        self.assertIn("1090", str(ctx.exception))
        self.assertIn("1024", str(ctx.exception))

    def test_the_optimizer_is_told_the_cap_it_is_held_to(self):
        self.improve(results([row("q", True, False)]))
        prompt = self.prompts()[0]["prompt"]
        self.assertIn("1024", prompt)
        self.assertIn("does not load", prompt)


class TestResponseParsing(OptimizerHarness):
    def test_tagged_response_is_extracted(self):
        self.control(optimizer_response="chatter\n" + tagged("the description") + "\nmore")
        self.assertEqual(self.improve(results([row("q", True, False)])), "the description")

    def test_untagged_response_falls_back_to_the_whole_text(self):
        self.control(optimizer_response="  a bare answer  ")
        self.assertEqual(self.improve(results([row("q", True, False)])), "a bare answer")

    def test_surrounding_quotes_are_stripped(self):
        self.control(optimizer_response=tagged('"a quoted answer"'))
        self.assertEqual(self.improve(results([row("q", True, False)])), "a quoted answer")

    def test_a_multiline_description_survives(self):
        self.control(optimizer_response=tagged("line one\nline two"))
        self.assertEqual(self.improve(results([row("q", True, False)])), "line one\nline two")


class TestSubprocessContract(OptimizerHarness):
    def test_a_nonzero_exit_raises_with_the_child_stderr(self):
        self.control(optimizer_exit_code=1, optimizer_stderr="Invalid API key\n")
        with self.assertRaises(RuntimeError) as ctx:
            self.improve(results([row("q", True, False)]))
        self.assertIn("exited 1", str(ctx.exception))
        self.assertIn("Invalid API key", str(ctx.exception))

    def test_the_model_is_passed_through_to_the_cli(self):
        self.improve(results([row("q", True, False)]), model="claude-sonnet-4-5")
        argv = self.prompts()[0]["argv"]
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-sonnet-4-5")

    def test_the_prompt_travels_on_stdin_not_argv(self):
        """It embeds the whole SKILL.md body and would blow the argv limit."""
        self.improve(results([row("a very distinctive query string", True, False)]))
        record = self.prompts()[0]
        self.assertIn("a very distinctive query string", record["prompt"])
        self.assertNotIn("a very distinctive query string", " ".join(record["argv"]))

    def test_claudecode_is_stripped_so_nesting_works(self):
        os.environ["CLAUDECODE"] = "1"
        self.addCleanup(os.environ.pop, "CLAUDECODE", None)
        self.improve(results([row("q", True, False)]))
        self.assertEqual(len(self.prompts()), 1)


class TestPermissionPolicy(OptimizerHarness):
    """This call was the one `claude -p` in the tree with no permission control
    at all, and it is the looser of the two: a probe runs in a fresh temp
    directory under `--setting-sources project,local`, while this one inherits
    the caller's cwd -- the user's own repository -- and loads every settings
    scope. Its prompt embeds the whole SKILL.md body under test, which came from
    wherever the skill did.

    Argv only. Nothing here runs a model."""

    def test_the_optimizer_call_is_bounded_by_default(self):
        self.improve(results([row("q", True, False)]))
        argv = self.prompts()[0]["argv"]
        self.assertIn("--permission-mode", argv)
        self.assertEqual(
            argv[argv.index("--permission-mode") + 1], SAFE_PERMISSION_MODE
        )

    def test_the_rewrite_call_is_bounded_too(self):
        """The over-1024-character net makes a second billed session. It is a
        separate `_call_claude` and is exactly the one a threaded parameter
        gets forgotten in."""
        self.control(optimizer_responses=[tagged("L" * 1100), tagged("S" * 200)])
        self.improve(results([row("q", True, False)]))
        calls = self.prompts()
        self.assertEqual(len(calls), 2, calls)
        for call in calls:
            argv = call["argv"]
            self.assertEqual(
                argv[argv.index("--permission-mode") + 1], SAFE_PERMISSION_MODE
            )

    def test_none_means_no_opinion_and_lands_on_the_safe_mode(self):
        self.improve(results([row("q", True, False)]), permission_mode=None)
        argv = self.prompts()[0]["argv"]
        self.assertEqual(
            argv[argv.index("--permission-mode") + 1], SAFE_PERMISSION_MODE
        )

    def test_inheriting_host_permissions_needs_the_opt_in(self):
        with self.assertRaises(PermissionModeError) as ctx:
            self.improve(
                results([row("q", True, False)]),
                permission_mode=INHERIT_PERMISSION_MODE,
            )
        self.assertIn("--allow-host-permissions", str(ctx.exception))
        self.assertEqual(self.prompts(), [], "a session was bought under a refused mode")

    def test_the_opt_in_is_what_omits_the_flag(self):
        self.improve(
            results([row("q", True, False)]),
            permission_mode=INHERIT_PERMISSION_MODE,
            allow_host_permissions=True,
        )
        self.assertNotIn("--permission-mode", self.prompts()[0]["argv"])


class TestEncoding(OptimizerHarness):
    """C7. `subprocess.run(text=True)` without an explicit encoding uses
    `locale.getpreferredencoding` -- cp1252 on this project's reference machine.
    The prompt carries the *entire* SKILL.md body, so a single em dash or arrow
    raised UnicodeEncodeError before the child was spoken to at all. This was
    live in the tree and invisible because the file had no tests."""

    NASTY = "café — naïve → ±  中文  עברית  🙂"

    def test_non_ascii_skill_content_does_not_crash_the_call(self):
        out = improve_description(
            skill_name="widget-forge",
            skill_content=f"# Widget forge\n\n{self.NASTY}\n",
            current_description=CURRENT,
            eval_results=results([row("q", True, False)]),
            history=[],
            model="haiku",
        )
        self.assertTrue(out)
        self.assertIn(self.NASTY, self.prompts()[0]["prompt"])

    def test_non_ascii_query_text_reaches_the_optimizer_intact(self):
        self.improve(results([row(self.NASTY, True, False)]))
        self.assertIn(self.NASTY, self.prompts()[0]["prompt"])

    def test_a_non_ascii_answer_comes_back_intact(self):
        answer = "Utilisez ce skill pour les manifestes — 中文测试 ✓"
        self.control(optimizer_response=tagged(answer))
        self.assertEqual(self.improve(results([row("q", True, False)])), answer)


class TestTranscriptLog(OptimizerHarness):
    def test_transcript_records_the_call_and_is_valid_utf8(self):
        answer = "Utilisez — ✓"
        self.control(optimizer_response=tagged(answer))
        log_dir = self.tmp / "logs"
        self.improve(results([row("q", True, False)]), log_dir=log_dir, iteration=2)

        path = log_dir / "improve_iter_2.json"
        self.assertTrue(path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["iteration"], 2)
        self.assertEqual(data["parsed_description"], answer)
        self.assertEqual(data["final_description"], answer)
        self.assertEqual(data["char_count"], len(answer))
        self.assertFalse(data["over_limit"])
        # json.dumps defaults to ensure_ascii, so the file is pure ASCII and the
        # payload is recoverable by any JSON reader on any locale. Assert the
        # round trip, not the raw bytes -- the bytes are escapes by design.
        raw = path.read_bytes()
        self.assertEqual(raw.decode("utf-8"), raw.decode("ascii"))
        self.assertEqual(json.loads(raw.decode("utf-8"))["final_description"], answer)

    def test_transcript_records_both_halves_of_a_rewrite(self):
        self.control(optimizer_responses=[tagged("L" * 1100), tagged("S" * 200)])
        log_dir = self.tmp / "logs"
        self.improve(results([row("q", True, False)]), log_dir=log_dir, iteration=1)

        data = json.loads((log_dir / "improve_iter_1.json").read_text(encoding="utf-8"))
        self.assertTrue(data["over_limit"])
        self.assertEqual(data["char_count"], 1100)
        self.assertEqual(data["rewrite_char_count"], 200)
        self.assertFalse(data["over_limit_after_rewrite"])
        self.assertEqual(data["final_description"], "S" * 200)

    def test_a_refused_rewrite_is_still_logged_before_the_raise(self):
        """The call was paid for. Losing the transcript loses the evidence."""
        self.control(optimizer_responses=[tagged("L" * 1100), tagged("M" * 1090)])
        log_dir = self.tmp / "logs"
        with self.assertRaises(RuntimeError):
            self.improve(results([row("q", True, False)]), log_dir=log_dir, iteration=3)
        data = json.loads((log_dir / "improve_iter_3.json").read_text(encoding="utf-8"))
        self.assertTrue(data["over_limit_after_rewrite"])
        self.assertEqual(data["rewrite_char_count"], 1090)

    def test_nothing_is_written_when_no_log_dir_is_given(self):
        self.improve(results([row("q", True, False)]))
        self.assertEqual(list(self.tmp.glob("**/improve_iter_*.json")), [])


class TestCli(OptimizerHarness):
    """The CLI runs non-interactively, with stdin from NUL/devnull (C14)."""

    def _run(self, eval_results_payload, extra=()):
        eval_path = self.tmp / "eval-results.json"
        eval_path.write_text(json.dumps(eval_results_payload), encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-m", "scripts.improve_description",
             "--eval-results", str(eval_path),
             "--skill-path", str(FIXTURES / "probe-skill"),
             "--model", "haiku", *extra],
            cwd=str(SKILL_ROOT),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=120,
        )

    def _payload(self):
        payload = results([
            row("author a widget manifest", True, False),
            row("capital of France", False, True),
        ])
        payload["description"] = CURRENT
        return payload

    def test_cli_emits_the_new_description_and_history_as_json(self):
        self.control(optimizer_response=tagged("a fresh description"))
        proc = self._run(self._payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["description"], "a fresh description")
        self.assertEqual(len(out["history"]), 1)
        self.assertEqual(out["history"][0]["description"], CURRENT)
        self.assertEqual(out["history"][0]["passed"], 1)

    def test_cli_does_not_traceback_on_a_missing_skill(self):
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.improve_description",
             "--eval-results", str(self.tmp / "nope.json"),
             "--skill-path", str(self.tmp / "no-such-skill"),
             "--model", "haiku"],
            cwd=str(SKILL_ROOT), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("No SKILL.md found", proc.stderr)

    def test_cli_appends_to_a_history_file(self):
        self.control(optimizer_response=tagged("a fresh description"))
        history_path = self.tmp / "history.json"
        history_path.write_text(
            json.dumps([{"description": "an earlier attempt", "passed": 0,
                         "total": 2, "results": []}]),
            encoding="utf-8",
        )
        proc = self._run(self._payload(), extra=["--history", str(history_path)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(len(out["history"]), 2)
        self.assertEqual(out["history"][0]["description"], "an earlier attempt")

    def test_cli_stdout_carries_json_alone(self):
        """C6: --json-shaped stdout must never be corrupted by progress chatter."""
        self.control(optimizer_response=tagged("a fresh description"))
        proc = self._run(self._payload(), extra=["--verbose"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        json.loads(proc.stdout)
        self.assertIn("Current:", proc.stderr)

    def test_cli_bounds_the_call_without_being_asked_to(self):
        self.control(optimizer_response=tagged("a fresh description"))
        proc = self._run(self._payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        argv = self.prompts()[0]["argv"]
        self.assertEqual(
            argv[argv.index("--permission-mode") + 1], SAFE_PERMISSION_MODE
        )

    def test_cli_refuses_to_inherit_host_permissions_without_the_opt_in(self):
        self.control(optimizer_response=tagged("a fresh description"))
        proc = self._run(
            self._payload(), extra=["--permission-mode", INHERIT_PERMISSION_MODE]
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("--allow-host-permissions", proc.stderr)
        self.assertEqual(self.prompts(), [], "a session was bought under a refused mode")

    def test_cli_opt_in_reaches_the_child_and_says_so(self):
        self.control(optimizer_response=tagged("a fresh description"))
        proc = self._run(self._payload(), extra=[
            "--permission-mode", INHERIT_PERMISSION_MODE, "--allow-host-permissions",
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Warning:", proc.stderr)
        self.assertNotIn("--permission-mode", self.prompts()[0]["argv"])

    def test_cli_refuses_an_unknown_mode_as_a_usage_error(self):
        proc = self._run(self._payload(), extra=["--permission-mode", "readOnly"])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

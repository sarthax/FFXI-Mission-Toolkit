"""#1408: plain-language wording for the codes ``revision_comparison.compare_revisions`` can return.

Display only. A code with no entry is shown as itself with a note, never as a guess; a test keeps this table in step
with the comparison module so a new code cannot ship without wording.
"""
from __future__ import annotations

TRANSITIONS = {
    "REGRESSION_CANDIDATE": "Passed before, fails now. A candidate regression: the two recorded results differ, which does not show what caused it.",
    "FIXED_CANDIDATE": "Did not pass before (it failed), passes now. A candidate fix: the two recorded results differ, which does not show what caused it.",
    "UNCHANGED": "Same verdict in both runs.",
    "STILL_UNKNOWN": "No determination in either run.",
    "STILL_BLOCKED": "Blocked in both runs.",
    "UNBLOCKED": "Blocked before, a determination was reached now.",
    "NOW_ESTABLISHED": "No determination before, a verdict was recorded now.",
    "NOT_ESTABLISHED": "A verdict was recorded before, but the later run did not establish one.",
    "ENVIRONMENT_BLOCKED": "Newly blocked because the test environment was not available.",
    "FIXTURE_ABSENT": "Newly blocked because a required fixture was not present.",
    "ORACLE_UNKNOWN": "Newly blocked because there is no established way to decide pass or fail.",
    "BLOCKED_OTHER": "Newly blocked for another cause.",
    "SKIPPED": "One of the runs was skipped, so nothing was compared.",
    "NO_BASELINE": "Only the later run has a result for this case, so there is nothing to compare it with.",
    "NOT_COMPARABLE": "These two results cannot be compared, for the reasons listed.",
}
REASONS = {
    "DSP_COMMIT_INVALID_LEFT": "The earlier run's DSP revision is not a full commit identifier.",
    "DSP_COMMIT_INVALID_RIGHT": "The later run's DSP revision is not a full commit identifier.",
    "UNCLASSIFIED_BLOCK_LEFT": "The earlier run was blocked with no recorded reason.",
    "UNCLASSIFIED_BLOCK_RIGHT": "The later run was blocked with no recorded reason.",
    "SAME_DSP_REVISION": "Both runs used the same DSP revision, so this is a re-run, not a comparison across revisions.",
    "DEFINITION_DIGEST_MISSING": "The test definition was not fingerprinted when one of the runs was imported (older import).",
    "DEFINITION_CHANGED": "The test definition changed between the two runs.",
    "ENVIRONMENT_FINGERPRINT_MISSING": "One or both runs did not record which test environment they used.",
    "ENVIRONMENT_MISMATCH": "The two runs used different test environments.",
    "FIXTURE_CONTEXT_MISSING": "One or both runs did not record their test fixtures.",
    "FIXTURE_CONTEXT_MISMATCH": "The two runs used different test fixtures.",
    "SCHEMA_VERSION_MISSING": "The evidence format version was not recorded for one or both runs.",
    "SCHEMA_DRIFT": "The two runs used different evidence formats.",
    "NO_RECORD_LEFT": "The earlier run has no result for this case.",
    "NO_RECORD_RIGHT": "The later run has no result for this case. That is not a pass, a failure or a regression.",
}


def transition_text(code: str) -> str:
    return TRANSITIONS.get(code, f"{code} (no description available for this code).")


def reason_text(code: str) -> str:
    return REASONS.get(code, f"{code} (no description available for this code).")

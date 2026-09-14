# dsp-engine-changes/ — README template

This is a **template**, not a real example — real engine-change writeups belong to your own
backport project's history, not this bundled scaffold. Copy this structure for each new C++
engine capability your backport work adds to a DSP checkout.

## What to change was needed

Describe the real gap: what Lua binding/behavior did the source codebase (e.g. Topaz) have that
the DSP target didn't, confirmed by reading the real source on both sides (not assumed).

## What was actually added

The real, scoped C++ change — new binding registration, new engine plumbing, whatever it was.
Cite real file paths and line numbers on both sides.

## Verification

How it was actually confirmed to work — built clean, tested live, matches an existing equivalent
elsewhere in the same codebase, etc. Evidence, not assertion.

## The `.diff`

Alongside this `README.md`, include one real `.diff` (via `git diff` against the target DSP
checkout's working tree, scoped to just this change's hunks if other unrelated changes share the
same file) — the durable record of the change, independent of whether the target checkout's own
working tree ever gets reset.

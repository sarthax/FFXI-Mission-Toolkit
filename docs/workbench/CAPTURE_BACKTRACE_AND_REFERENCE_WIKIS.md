# Capture Backtrace and Dual-Wiki Evidence

## Capture → implementation backtrace

A capture can be the root of a reverse dependency investigation:

```text
capture
  → event / message-or-CSID identifier
  → packet
  → NPC / mob / spawn / action
  → server data
  → Lua
  → binding
  → C++
  → enum/constants
  → build target
  → target-server implementation

and independently:

capture
  → observed packet / event / asset requirement
  → client capability
  → DAT / EXE / DLL
  → target-client support
```

A capture proves that something occurred on a particular client/server combination. It does not prove that the target checkout can reproduce it. The backtrace therefore distinguishes PRESENT, MISSING, AMBIGUOUS, and UNKNOWN rather than turning an absent index entry into a false negative.

`capture_backtrace.py` is the first reverse-direction checker. As more canonical relationships are connected, the same capture can be traced farther without changing the capture ingestion format.

### CSID/message handling

Capture numeric identifiers are initially kept as `MESSAGE_OR_EVENT_ID`. They should only become a confirmed CSID when packet/event evidence establishes that semantic mapping. This avoids incorrectly treating a packet message number as a Lua `startEvent(N)` or `csid == N`.

## FFXIclopedia as a second reference source

FFXIclopedia is maintained as a separate reference source rather than merged into BG Wiki. Its public site describes a large FFXI encyclopedia with information covering missions, quests, NPCs, creatures, locations, systems and other game data.

The adapter stores source ID, page ID, revision ID/timestamp, page text, and a content hash. A MediaWiki XML export is the preferred reproducible offline input; MediaWiki documents XML export as a portable format suitable for analysis.

Future comparison records should preserve both sources independently:

- `BGWiki`
- `FFXIclopedia`

For aligned facts, show both evidence sources. For disagreement, create a `REFERENCE_CONFLICT` finding containing both values plus source/revision metadata. Do not silently select a winner.

The reference layer remains below server/client/runtime evidence:

```text
server source / DB / C++
client DAT / EXE / DLL
packet / capture
reference: BG Wiki
reference: FFXIclopedia
derived / inferred
```

This allows the two wikis to fill gaps in one another while keeping disagreement visible.

# Opt-in Ashita GM command response capture

This is a **developer-only, unmodified-server** integration with the bundled
`addons/workbench_live` Lua addon. It requires an active authenticated Live
Bridge connection and the existing GM command to be supported on the server.

## Manual smoke test

1. Update the bundled Ashita addon files, including the new
   `workbench_gm_capture.lua`, and restart/reload the addon.
2. Start the configured local Live Bridge using the existing `/wblive`
   bridge commands. Verify the bridge is active.
3. As a permitted GM in-game, enter `/wblive gm arm`. The capture is
   single-use and expires after 20 seconds.
4. Enter `!getmobaction <global-mob-id>` and inspect normal in-game chat.
5. If the text matches the verified form
   `<mob name> <numeric ID> current action ID is <numeric action>`,
   the addon sends the response as a `capture/capture_event` frame
   through the existing authenticated loopback bridge.
6. Enter `/wblive gm stop` to cancel capture.

The filter does **not** forward unrelated tells, party, linkshell or shout
messages. It never auto-sends GM commands and does not block incoming game
text. The payload includes the response and timestamp but the response is
still advisory, not authoritative spawn-state evidence.

## Known gaps

The bridge listener already supports bounded capture lanes via
`BridgeMailbox`. This slice delivers events to that lane but does **not**
yet wire mailbox retrieval or GM response history into the 3D Inspector.
Incoming text callback fields and exact GM chat formatting must be checked
in a live Ashita v4 session; the filter intentionally fails closed rather
than capturing broad chat. Future work: bounded capture-event consumer and
inspector evidence display with explicit session/zone provenance.

# Ashita v4 real movement — verification checklist

The existing Ashita bridge is telemetry-only. The control envelope and priority mailbox already exist. The new MovementControlGate rejects simulated nudges and has **no game-write path**.

Before real movement:
1. Identify the loaded Ashita v4 and FFXI module revisions, and verify a documented v4 memory-write or plugin interface. Ashita v3 examples alone are insufficient.
2. Prove which XYZ/heading memory fields are read versus written, and how client refresh or server correction behaves.
3. Investigate outgoing packet injection independently. Sending packets is not evidence of server-accepted movement.
4. Test only an authorized disposable DSP/Topaz character and compare client readback to independent server-side position.
5. Disarm on wrong client, stale telemetry, zone change, reconnect, logout, excessive nudge or missing version verification. STOP must not depend on capture throughput.
6. Add a versioned bidirectional bridge control exchange and synthetic two-client simulations *before* real Ashita writes.
7. Only then connect 3D destination selection to a small opt-in nudge, verified progress, assisted travel, and canonical Capture research.

**Unverified:** actual Ashita v4 player-position writes, injected movement packet format, server acceptance and collision bypass. No claim of live movement until witnessed in-game.

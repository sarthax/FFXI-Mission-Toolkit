"""Standalone offline HTML reviewer; no Workbench route or editor modifications.

Usage (operator-owned local indexed database, READ ONLY):
    python -m workbench.captures.scenario_review_offline \
        --database path/to/capture-index.sqlite --capture-id 1 --output review.html

The output file is a standalone private review artifact containing indexed
metadata, hashes and evidence references. Keep it in a trusted local location.
The HTML only exports a review JSON bundle; it never saves a canonical spec,
calls a server, fetches data, or launches a gameplay action.
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import sqlite3

from .scenario_handoff import reconstruct_review_draft
from .scenario_review_workflow import manual_editor_handoff
from .scenario_readiness_summary import (summarize_capture_readiness, _observations,
                                         _typed_authoring_projection)
from .scenario_identity_readiness import _observation_digest


def _json(data: object) -> str:
    """Prevent embedded capture strings from ending the script element."""
    return (json.dumps(data, ensure_ascii=True, sort_keys=True)
            .replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026"))


def render_review_html(draft: dict, *, readiness: dict | None = None) -> str:
    """Display read-only readiness in the existing offline reviewer; no approval."""
    bundle = manual_editor_handoff(draft)
    if readiness is None:
        readiness = summarize_capture_readiness(draft)
    if (not isinstance(readiness, dict)
            or readiness.get("contract") != "capture_author_readiness_summary_v0_NONCANONICAL"
            or readiness.get("capture_id") != draft["capture_id"]
            or readiness.get("capture_projection_sha256") != _observation_digest(draft)
            or readiness.get("execution_enabled") is not False
            or readiness.get("normative_expected") is not None
            or readiness.get("verdict") != "UNKNOWN"
            or not isinstance(readiness.get("readiness_steps"), list)
            or len(readiness["readiness_steps"]) != len(draft["steps"])
            or {x.get("step_id") for x in readiness["readiness_steps"]} !=
               {x["step_id"] for x in draft["steps"]}):
        raise ValueError("readiness summary does not match the indexed capture draft")
    readiness_by_step = {s["step_id"]: s for s in readiness["readiness_steps"]}
    if (not isinstance(readiness.get("source_integrity"), dict)
            or not isinstance(readiness.get("scenario_developer_handoff"), dict)):
        raise ValueError("invalid source integrity or authoring-readiness envelope")
    # The optional companion for Agent B is display-only and derived from
    # these exact reviewer steps; reject invented approval/permissions.
    expected_authoring = _typed_authoring_projection(
        draft["capture_id"], readiness["capture_projection_sha256"],
        readiness["readiness_steps"], readiness["source_integrity"],
        draft["evidence_map"],
    )
    if (readiness.get("scenario_developer_handoff", {}).get("read_only_projection")
            != expected_authoring):
        raise ValueError("authoring-readiness projection changed or claims new authority")
    if (not isinstance(readiness.get("source_integrity"), dict)
            or readiness["source_integrity"].get("independent_capture_bytes_authenticated") is not False
            or readiness["source_integrity"].get("state") not in {"UNKNOWN", "BLOCKED"}
            or any(
                not isinstance(summary.get("missing_observations"), list)
                or summary.get("readiness_state") not in {"UNKNOWN", "BLOCKED"}
                or summary["missing_observations"] != [
                    {**gap, "readiness_state": summary["readiness_state"]}
                    for gap in _observations(original)
                ]
                for original, summary in zip(draft["steps"], readiness["readiness_steps"], strict=True)
            )):
        raise ValueError("readiness gaps cannot claim independent readbacks or granted permissions")
    if (readiness.get("approved_for_execution") is not False
            or readiness.get("scenario_developer_handoff", {}).get("automatic_import") is not False
            or readiness.get("scenario_developer_handoff", {}).get("save_allowed") is not False
            or readiness.get("contract_v2_alignment", {}).get("automatic_import") is not False
            or readiness.get("contract_v2_alignment", {}).get("execution_enabled") is not False
            or any(x.get("normative_expected") is not None or x.get("verdict") != "UNKNOWN"
                   or x.get("execution_enabled") is not False
                   or x.get("independently_verified_client_dsp_identity") is not False
                   or x.get("evidence_refs") != next(
                       z["evidence_refs"] for z in draft["steps"] if z["step_id"] == x["step_id"])
                   or x.get("oracle_readiness", {}).get("normative_expected") is not None
                   or any(b.get("source_identity_verified") is not False
                          for b in x.get("identity_matches", []))
                   or any(not set(m.get("evidence_refs", [])).issubset(set(x["evidence_refs"]))
                          for m in x.get("missing_observations", []))
                   for x in readiness["readiness_steps"])):
        raise ValueError("unsafe readiness summary cannot be displayed or exported")
    if len(json.dumps(readiness, ensure_ascii=True).encode("utf-8")) > 4_000_000:
        raise ValueError("readiness advisory too large for offline export")
    if len(json.dumps(bundle, ensure_ascii=True).encode("utf-8")) > 4_000_000:
        raise ValueError("review export too large; reduce indexed row caps")
    ui = []
    for lane in bundle["timeline"]["lanes"]:
        ui.append("<section class='lane'><h2>" + escape(lane["table"])
                  + " · zone " + escape(str(lane["zone_label"]))
                  + "</h2><p class='warn'>Source-local order only: "
                  + escape(lane["order_basis"]) + "; cross-stream clocks unaligned.</p>")
        for event in lane["events"]:
            sid = event["step_id"]
            related = next(s for s in draft["steps"] if s["step_id"] == sid)
            ui.append("<article class='event'><h3>" + escape(sid) + " — "
                      + escape(event["summary"]) + "</h3>")
            ui.append("<p><strong>Interpretation:</strong> " + escape(event["interpretation"])
                      + " · <strong>Record:</strong> " + escape(event["record_class"]) + "</p>")
            if event["gaps"]:
                ui.append("<p class='warn'>Unresolved: " + escape(", ".join(event["gaps"])) + "</p>")
            diagnostic = readiness_by_step[sid]
            ui.append(
                "<details><summary>Identity and oracle readiness — "
                + escape(diagnostic["expected_outcome_classification"])
                + " · verdict UNKNOWN</summary>"
                + "<p>Exact source-record match is NOT independent client/DSP verification. "
                  "Candidate source expectations are NOT approved oracles.</p>"
                + "<pre>" + escape(json.dumps({
                    "identity_matches": diagnostic["identity_matches"],
                    "missing_observations": diagnostic["missing_observations"],
                    "missing_provenance_and_review": diagnostic["missing_provenance_and_review"],
                    "oracle_readiness": diagnostic["oracle_readiness"],
                    "compatibility_issues": diagnostic["compatibility_issues"],
                }, sort_keys=True, indent=2, ensure_ascii=True))
                + "</pre></details>"
            )
            ui.append("<div class='review'><label>Step review <select class='step-decision' data-id='"
                      + escape(sid, quote=True) + "'><option value='PENDING'>Pending</option>"
                      + "<option value='ACCEPT'>Accept proposed summary</option>"
                      + "<option value='EDIT'>Edit proposed title</option>"
                      + "<option value='REJECT'>Reject proposed step</option></select></label>"
                      + "<label>Edited title (EDIT only) <input class='step-edit' data-id='"
                      + escape(sid, quote=True) + "' maxlength='500'></label>"
                      + "<label>Reason <input class='step-note' data-id='"
                      + escape(sid, quote=True) + "' maxlength='500'></label></div>")
            for binding in related["bindings"]:
                bid = escape(binding["binding_id"], quote=True)
                ui.append("<div class='binding'><p><b>" + escape(binding["kind"])
                          + "</b> · <span class='classification'>"
                          + escape(binding["classification"]) + "</span>"
                          + " · as indexed: <code>" + escape(json.dumps(binding["observed_value"], ensure_ascii=True))
                          + "</code></p><p>" + escape(binding["basis"]) + "</p>"
                          + "<div class='review'><label>Binding decision <select class='binding-decision' data-id='"
                          + bid + "'><option value='PENDING'>Pending</option>"
                          + "<option value='ACCEPT'>Accept as candidate</option>"
                          + "<option value='EDIT'>Edit candidate value</option>"
                          + "<option value='REJECT'>Reject proposed binding</option></select></label>"
                          + "<label>Edited candidate (EDIT only) <input class='binding-edit' data-id='"
                          + bid + "' maxlength='120'></label>"
                          + "<label>Reason <input class='binding-note' data-id='"
                          + bid + "' maxlength='500'></label></div></div>")
            ui.append("<details><summary>Original indexed evidence / SHA-256 / parser version / packet metadata</summary>"
                      + "<pre>" + escape(json.dumps(event["sources"], indent=2, sort_keys=True, ensure_ascii=True))
                      + "</pre></details></article>")
        ui.append("</section>")
    bdd = bundle["proposed_behavior"]
    bdd_html = []
    for phase in ("given", "when", "then"):
        bdd_html.append("<h3>" + phase.title() + " — provisional only</h3><ol>")
        for note in bdd[phase]:
            bdd_html.append("<li>" + escape(note) + "</li>")
        bdd_html.append("</ol>")
    associations = bundle["timeline"]["candidate_associations"]
    related_html = "<p>No cross-source candidates with identical recorded zone labels.</p>"
    if associations:
        related_html = "<ul>" + "".join(
            "<li>" + escape(x["left_step_id"]) + " ↔ " + escape(x["right_step_id"])
            + " · " + escape(x["basis"]) + " · INFERRED (not causal or independently verified)</li>"
            for x in associations
        ) + "</ul>"
    markup = """
<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<meta http-equiv='Content-Security-Policy'
 content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; form-action 'none'; object-src 'none'; base-uri 'none'">
<title>Evidence-to-Scenario — offline review</title>
<style>
body {font-family:system-ui,Arial,sans-serif;margin:2rem auto;max-width:1080px;padding:0 1rem;line-height:1.5}
h1,h2,h3 {line-height:1.25} h2 {margin-top:2rem}
.event {border:1px solid #aaa;border-radius:8px;margin:1rem 0;padding:1rem}
.binding {margin:0.7rem 0;padding:0.5rem 0.8rem;background:#f3f4f6;border-left:3px solid #666}
.review {display:flex;flex-wrap:wrap;gap:0.8rem;margin:1rem 0}
label {display:flex;flex-direction:column;font-size:.9rem;min-width:170px;flex:1}
input,select,button {font:inherit;padding:0.45rem}
input {max-width:300px}.warn {color:#7c3100}.lane {border-top:2px solid #888}
pre {white-space:pre-wrap;overflow-wrap:anywhere;font-size:.82rem}
button {cursor:pointer;margin:0.5rem 0}
code {overflow-wrap:anywhere}
footer {padding:2rem 0} .classification {font-weight:700}
</style></head><body>
<h1>Evidence-to-Scenario — offline human review</h1>
<p class='warn'><strong>OBSERVED ONLY · UNKNOWN normative outcome · NO EXECUTION.</strong>
No packet decode or live client access. Indexed file hashes do not authenticate the physical raw source.
Different streams have no independently established common clock or causal relationship.</p>
<section><h2>Provisional Given / When / Then</h2>
BDD_PLACEHOLDER
<p class='warn'>These phrases describe observed evidence or the review task, not authoritative requirements.</p></section>
<section><h2>Candidate cross-source associations</h2>
<p>Same captured zone label or entity field is only a tentative investigation link.
No global chronology or source namespace identity is implied.</p>
ASSOCIATIONS_PLACEHOLDER</section>
<section><h2>Reconstructed timeline — separate source lanes</h2>EVENTS_PLACEHOLDER</section>
<section><h2>Readiness summary</h2>
<p>Read-only diagnostics, with no source authenticity or oracle approval implied.
Offline source-file hashes require independent validation. No gameplay run was performed.</p>
READINESS_PLACEHOLDER</section>
<section><h2>Continue in Scenario Developer</h2>
<p><strong>Manual handoff only.</strong> Export a design-only review bundle below,
then open Scenario Developer yourself. Independently bind canonical IDs and
a pinned DSP source:file:line oracle, preconditions, cleanup and readbacks.
The exported JSON is <strong>not</strong> a validatable or savable canonical
scenario, and must never be sent to a runner or import endpoint unchanged.</p>
<p><button id='export'>Export design-only review JSON</button>
<button id='export-advisory'>Export separate readiness sidecar (no automatic import)</button>
<span id='status' role='status' aria-live='polite'></span></p>
</section><footer>All reviewer changes remain in this page until exported manually.
Original indexed observations and hashes are preserved separately from all reviewer decisions.</footer>
<script id='bundle' type='application/json'>DATA_PLACEHOLDER</script>
<script id='readiness' type='application/json'>READINESS_JSON_PLACEHOLDER</script>
<script>
'use strict';
const ORIGINAL = JSON.parse(document.getElementById('bundle').textContent);
const READINESS = JSON.parse(document.getElementById('readiness').textContent);
function field(cls, id) {
  return [...document.querySelectorAll('.'+cls)].find(e => e.dataset.id === id)?.value ?? '';
}
function gather() {
  const steps = [];
  const bindings = [];
  for (const s of ORIGINAL.reviewed_steps) {
    const decision = field('step-decision',s.step_id);
    const note = field('step-note',s.step_id).trim();
    const title = field('step-edit',s.step_id).trim();
    if (decision !== 'PENDING') {
      if (!note) throw Error('Reviewer note required for step '+s.step_id);
      if (decision === 'EDIT' && !title) throw Error('Edited title required for '+s.step_id);
      const record = {step_id:s.step_id,decision,note};
      if (decision === 'EDIT') record.edited_title = title;
      steps.push(record);
    }
    for (const b of s.bindings) {
      const bdecision = field('binding-decision',b.binding_id);
      const bnote = field('binding-note',b.binding_id).trim();
      const edited = field('binding-edit',b.binding_id).trim();
      if (bdecision !== 'PENDING') {
        if (!bnote) throw Error('Reviewer note required for binding '+b.binding_id);
        if (bdecision === 'EDIT' && !edited) throw Error('Edited value required for '+b.binding_id);
        const record = {binding_id:b.binding_id,decision:bdecision,note:bnote};
        if (bdecision === 'EDIT') record.edited_value = edited;
        bindings.push(record);
      }
    }
  }
  return {steps,bindings};
}
document.getElementById('export').addEventListener('click', () => {
  const status = document.getElementById('status');
  try {
    const decisions = gather();
    // A review submission is untrusted user input, not proof of approval.
    const payload = {
      contract:'offline_capture_review_decisions_v1_NONCANONICAL',
      capture_id:ORIGINAL.capture_id,
      capture_projection_sha256:ORIGINAL.capture_projection_sha256,
      observed_handoff:ORIGINAL,
      step_decisions:decisions.steps, binding_decisions:decisions.bindings,
      review_status:'MANUAL_AUTHORING_REQUIRED',
      normative_expected:null,verdict:'UNKNOWN',
      execution_enabled:false,approved_for_execution:false
    };
    const blob = new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href=url;a.download='capture-'+String(ORIGINAL.capture_id)+'-design-only-review.json';
    document.body.appendChild(a);a.click();a.remove();
    // Delay revocation so browsers can finish initiating the local download.
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    status.textContent='Exported design-only review. No scenario saved or executed.';
  } catch (err) {status.textContent=err.message;}
});
document.getElementById('export-advisory').addEventListener('click', () => {
  const status = document.getElementById('status');
  try {
    // Separate advisory never alters the existing review-decision export or
    // claims canonical spec/import/permission authority.
    const sidecar = {
      contract:'capture_reviewer_readiness_sidecar_v0_NONCANONICAL',
      capture_id:ORIGINAL.capture_id,
      // These two tooling hashes cover different projections and are not
      // interchangeable cryptographic attestations of physical capture bytes.
      indexed_observation_projection_sha256:READINESS.capture_projection_sha256,
      original_handoff_projection_sha256:ORIGINAL.capture_projection_sha256,
      original_evidence_handoff:ORIGINAL,
      review_decisions:gather(),
      readiness_diagnostics:READINESS,
      scenario_developer_handoff:READINESS.scenario_developer_handoff,
      normative_expected:null,verdict:'UNKNOWN',
      automatic_import:false,approved_for_execution:false,execution_enabled:false
    };
    const blob = new Blob([JSON.stringify(sidecar,null,2)],{type:'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href=url;a.download='capture-'+String(ORIGINAL.capture_id)+'-readiness-advisory-only.json';
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    status.textContent='Exported separate noncanonical readiness sidecar. No import, save or execution.';
  } catch(err) {status.textContent=err.message;}
});
</script></body></html>"""
    return (markup.replace("BDD_PLACEHOLDER", "\n".join(bdd_html))
            .replace("ASSOCIATIONS_PLACEHOLDER", related_html)
            .replace("EVENTS_PLACEHOLDER", "\n".join(ui))
            .replace("READINESS_PLACEHOLDER", "<pre>" + escape(json.dumps({
                "source_integrity": readiness["source_integrity"],
                "repeated_capture_diagnostics": readiness["repeated_capture_diagnostics"],
                "contract_v2_alignment_status": readiness["contract_v2_alignment"]["status"],
                "handoff": readiness["scenario_developer_handoff"],
            }, indent=2, sort_keys=True, ensure_ascii=True)) + "</pre>")
            .replace("DATA_PLACEHOLDER", _json(bundle))
            .replace("READINESS_JSON_PLACEHOLDER", _json(readiness)))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Offline capture scenario review HTML (no source writes)")
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--capture-id", type=int, required=True)
    p.add_argument("--output", type=Path, required=True, help="Standalone local HTML review artifact")
    opts = p.parse_args(argv)
    database = opts.database.resolve(strict=True)
    output = opts.output.resolve()
    if database == output:
        raise ValueError("output must not overwrite the capture index")
    # read-only SQLite URI prevents even accidentally creating capture tables.
    uri = database.as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        con.execute("PRAGMA query_only=ON")
        draft = reconstruct_review_draft(con, opts.capture_id)
    finally:
        con.close()
    content = render_review_html(draft)
    if not output.parent.is_dir():
        raise ValueError("output parent must exist")
    output.write_text(content, encoding="utf-8")
    print("Wrote offline design-only review HTML:", output)


if __name__ == "__main__":
    main()

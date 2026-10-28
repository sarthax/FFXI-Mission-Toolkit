/* R7 #1313: editor integration wiring checks, paired with real DOM disposal tests. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const script=fs.readFileSync('gui/static/scenario_developer.js','utf8');
const template=fs.readFileSync('gui/templates/scenario_developer.html','utf8');
const router=fs.readFileSync('src/workbench/server_admin/scenario_authoring/editor_router.py','utf8');
assert.match(template,/id="sd-readiness-viewer"/);
assert.ok(template.indexOf('/static/scenario_readiness_viewer.js')<
          template.indexOf('/static/scenario_developer.js'));
assert.match(script,/let readinessViewer = null/);
assert.match(script,/readinessViewer\.dispose\(\)/);
assert.match(script,/window\.addEventListener\('pagehide'/);
// #1393: a back/forward-cache restore must remount the viewer so stale file selections are not shown.
assert.match(script,/window\.addEventListener\('pageshow',event=>\{\s*if\(event\.persisted\)resetReadinessViewer\(\);/);
assert.match(script,/if\(mode!==target\)resetReadinessViewer\(\)/);
assert.match(script,/function resetReadinessViewer\(\)/);
assert.match(script,/ScenarioReadinessViewer\.mount\(\$\('sd-readiness-viewer'\)/);
assert.match(script,/handoff\/readiness\/inspect/);
const replacements=script.match(/editorGeneration\+\+;resetReadinessViewer\(\);/g)||[];
assert.equal(replacements.length,5,'Every existing document-replacement transition must invalidate the viewer');
assert.doesNotMatch(script,/handoff\/evidence\/inspect['"],'POST',\{review,sidecar\}/);
assert.match(router,/return inspect_paired_readiness\(body\.review, body\.sidecar\)/);
assert.match(router,/Invalid capture readiness JSON: non-finite or unsupported value/);
console.log('R7 editor attachment route, opt-in panel, transition disposal wiring: PASS');

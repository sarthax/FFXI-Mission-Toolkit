'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const catalog=JSON.parse(fs.readFileSync(path.join(root,'feature_catalog/features.json'),'utf8'));
const help=fs.readFileSync(path.join(root,'gui/templates/help.html'),'utf8');
test('only one design-only Scenario Developer capability has stable navigable help',()=>{
 const matches=catalog.features.filter(x=>x.id==='scenario-developer-design-only');
 assert.equal(matches.length,1);
 assert.equal(matches[0].route,'/scenario-developer');
 assert.equal(matches[0].help,'/help#help-feature-testing');
 assert.match(matches[0].caveat,/PRODUCT NOT ACCEPTED/);
 assert.match(help,/id="help-feature-testing"/);
});
test('different catalogs, validation records and non-executable draft are distinguished',()=>{
 for(const route of ['/feature-catalog','/feature-testing?tab=catalog','/scenario-developer','/validation/runs'])assert.ok(help.includes('href="'+route+'"'),route);
 assert.match(help,/draft-to-catalog Publish action/);
 assert.match(help,/arbitrary scenario RUN action/);
 assert.match(help,/no hosted UI route or button/);
 assert.match(help,/native beforeunload dialog appearance/);
 assert.match(help,/#1403/);
});

test('typed steps and run results are described accurately and stay design-only/read-only',()=>{
 for(const phrase of [/Typed steps \(design-only\)/,/Add Action Step/,/Add Check Step/,/acceptance only/,/nothing here sends anything to a game client/,/read-only <em>When \/ Then<\/em> preview/,/Compare with another run/,/never a cause/,/What happened/])assert.match(help,phrase,String(phrase));
 // the stated step limit must be the code's limit
 const lib=fs.readFileSync(path.join(root,'src/workbench/server_admin/feature_testing/typed_action_library.py'),'utf8');
 const limit=lib.match(/MAX_NATIVE_STEPS\s*=\s*(\d+)/);
 assert.ok(limit,'MAX_NATIVE_STEPS not found');
 assert.match(help,new RegExp('1 to '+limit[1]+' per draft'));
 // new catalog entries: one each, valid parent, existing referenced files, honest status
 for(const [id,parent] of [['scenario-developer-typed-steps','scenario-developer-design-only'],['testing-run-results','feature-testing']]){
  const rows=catalog.features.filter(x=>x.id===id);
  assert.equal(rows.length,1,id);
  assert.equal(rows[0].parent_id,parent);
  assert.ok(catalog.features.some(x=>x.id===parent),'parent exists: '+parent);
  assert.equal(rows[0].implementation,'partial');
  assert.equal(rows[0].validation,'unverified');
  assert.equal(rows[0].help,'/help#help-feature-testing');
  for(const ref of [...rows[0].source_refs,...rows[0].test_refs])assert.ok(fs.existsSync(path.join(root,ref)),'missing '+ref);
 }
 assert.match(catalog.features.find(x=>x.id==='scenario-developer-typed-steps').caveat,/does not prove the runner executes/);
 assert.match(catalog.features.find(x=>x.id==='testing-run-results').caveat,/never shows a cause/);
 // the product is still not accepted: the banner must not be softened by the new text
 assert.match(help,/Scenario authoring product NOT ACCEPTED \/ execution BLOCKED/);
});

test('the Test catalog is described as design-only: saved drafts can be added, nothing can be published from the UI',()=>{
 assert.match(help,/Add selected saved draft to the Test catalog/);
 assert.match(help,/not unsaved edits/);
 assert.match(help,/draft-to-catalog Publish action/);
 assert.match(help,/publishing only records that review decision/);
 assert.match(help,/draft-to-catalog Publish action that makes a scenario runnable/);
 const row=catalog.features.find(x=>x.id==='scenario-developer-design-only');
 assert.match(row.how_to_use,/Add to catalog/);
 assert.match(row.caveat,/PRODUCT NOT ACCEPTED/);
});

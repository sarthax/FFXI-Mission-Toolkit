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

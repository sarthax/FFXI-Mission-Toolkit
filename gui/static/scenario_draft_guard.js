/* #1333 -- single, browser-native unsaved draft lifecycle guard.
 * Pure state and beforeunload policy. No persistence, execution or editor replacement.
 */
(function(root,factory){
  const api=factory();
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.ScenarioDraftGuard=api;
})(typeof window!=='undefined'?window:this,function(){
  'use strict';
  const clone=value=>JSON.parse(JSON.stringify(value));
  const origins=new Set(['new','fork','clone','handoff','saved']);
  function create({win,getCurrent,getBaseline,getRevision,isSavePending,onStatus}){
    if(!win||typeof win.addEventListener!=='function'||
       [getCurrent,getBaseline,getRevision,isSavePending,onStatus].some(f=>typeof f!=='function'))
      throw Error('Unsaved guard requires an existing editor and window');
    let origin='new',starting=null,disposed=false;
    function inspect(){
      if(disposed)return {state:'pristine',warn:false,detail:'Guard closed',banner:''};
      let value=null,invalid=false;
      try {value=getCurrent();if(!value||typeof value!=='object')invalid=true;}
      catch(_e){invalid=true;}
      const baseline=getBaseline(),revision=getRevision(),pending=Boolean(isSavePending());
      const saved=baseline!==null&&baseline!==undefined;
      const same=!invalid&&saved&&JSON.stringify(value)===JSON.stringify(baseline);
      const pristine=!invalid&&!saved&&origin==='new'&&starting!==null&&
        JSON.stringify(value)===JSON.stringify(starting);
      let state=same&&!pending?'saved':pristine&&!pending?'pristine':'unsaved';
      // Invalid raw Advanced text and in-flight saves must never clear protection.
      if(invalid||pending)state='unsaved';
      let detail,banner;
      if(state==='saved'){
        detail='Saved revision '+revision+' · no changes';
        banner='SAVED · no unsaved changes';
      }else if(state==='pristine'){
        detail='New draft · pristine, not yet saved (revision 0)';
        banner='PRISTINE · new design (not saved)';
      }else{
        const context=saved?'revision '+revision:origin==='fork'?'forked draft':
          origin==='clone'?'cloned draft':origin==='handoff'?'source-derived draft':'new draft';
        detail='UNSAVED '+context+
          (invalid?' · Advanced JSON invalid (keep editing)':
           pending?' · save not yet confirmed':' · changes not saved');
        banner='UNSAVED WORK · leaving this page will discard changes';
      }
      return {state,warn:state==='unsaved',detail,banner,invalid,pending,origin};
    }
    function refresh(){
      const current=inspect();
      if(!disposed)onStatus(current);
      return current;
    }
    // A single native beforeunload handler protects browser reload, Back,
    // closing the tab and normal same-origin/full-page links. Do not also
    // intercept anchor clicks: that causes duplicate prompts and stale bypass.
    function beforeunload(event){
      if(!inspect().warn)return;
      event.preventDefault();
      event.returnValue=''; // browsers may show their own generic warning
    }
    win.addEventListener('beforeunload',beforeunload);
    function start(nextOrigin,snapshot){
      if(disposed)throw Error('Guard is disposed');
      if(!origins.has(nextOrigin)||!snapshot||typeof snapshot!=='object'||Array.isArray(snapshot))
        throw Error('Invalid draft origin or initial snapshot');
      origin=nextOrigin;
      starting=clone(snapshot);
      return refresh();
    }
    function dispose(){
      if(disposed)return;
      disposed=true;
      win.removeEventListener('beforeunload',beforeunload);
    }
    return {inspect,refresh,start,dispose};
  }
  return {create};
});

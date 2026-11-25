/* Verify the reported scroll jump with disposable mixed-state event data. */
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const repo=path.resolve(__dirname,'..');process.env.PLAYWRIGHT_BROWSERS_PATH??=path.join(repo,'node_modules/.cache/ms-playwright');
const {chromium}=require('playwright'),out=path.join(repo,'test-results','filters-'+Date.now());fs.mkdirSync(out,{recursive:true});
const data=path.join(out,'data'),py=process.env.VOTELAB_PYTHON||'python',log=fs.openSync(path.join(out,'server.log'),'w');
const server=spawn(py,['-u',path.join(__dirname,'ui-fixture.py'),data,'--filters'],{cwd:repo,env:process.env,stdio:['ignore',log,log],windowsHide:true});
const checks=[],errors=[],ok=(value,name)=>{if(!value)throw Error(name);checks.push(name);},wait=ms=>new Promise(r=>setTimeout(r,ms));let browser;
(async()=>{
 let state;for(let i=0;i<200;i++){if(fs.existsSync(path.join(data,'running-instance.json'))){state=JSON.parse(fs.readFileSync(path.join(data,'running-instance.json')));break;}if(server.exitCode!==null)throw Error(fs.readFileSync(path.join(out,'server.log'),'utf8'));await wait(100);}if(!state)throw Error('No fixture');
 const base='http://127.0.0.1:'+state.port,fixture=JSON.parse(fs.readFileSync(path.join(data,'fixture.json')));
 browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:900}});
 await context.addCookies(Object.entries(fixture.owner).map(([name,value])=>({name,value,url:base})));
 const p=await context.newPage();p.on('pageerror',e=>errors.push(e.message));
 await p.goto(base+'/?status=OPEN');await p.waitForLoadState('networkidle');
 ok(await p.locator('[data-event-list] .event-card:visible').count()===2,'direct Voting URL shows only open events');
 for(const viewport of [{width:1440,height:900},{width:390,height:844}]){
  await p.setViewportSize(viewport);await p.evaluate(()=>{const bar=document.querySelector('[data-event-list] .toolbar');scrollTo(0,scrollY+bar.getBoundingClientRect().top-150);window.filterMarker='same document';});
  const before=await p.evaluate(()=>scrollY),size=viewport.width;
  await p.screenshot({path:path.join(out,size+'-before.png')});
  await p.locator('[data-event-filter=ENTRIES]').click();
  ok(Math.abs(await p.evaluate(()=>scrollY)-before)<=1,size+': Voting to Applications keeps scroll position');
  ok(await p.locator('.event-card:visible').count()===1&&await p.locator('.event-card:visible').getAttribute('data-phase')==='ENTRIES',size+': correct applications displayed');
  ok(await p.evaluate(()=>window.filterMarker)==='same document',size+': filter does not reload document');
  await p.screenshot({path:path.join(out,size+'-applications.png')});
  await p.locator('[data-event-filter=CLOSED]').click();ok(await p.locator('.event-card:visible').count()===1&&await p.locator('.event-card:visible').getAttribute('data-phase')==='CLOSED',size+': closed filter is correct');
  await p.goBack();ok(await p.locator('[data-event-filter=ENTRIES]').getAttribute('aria-current')==='page',size+': browser Back restores filter');
  await p.locator('[data-search]').fill('no matching title');ok(await p.locator('[data-no-matches]').isVisible(),size+': combined search has clear empty feedback');
  const emptyY=await p.evaluate(()=>scrollY);await p.locator('[data-event-filter=OPEN]').click();ok(Math.abs(await p.evaluate(()=>scrollY)-emptyY)<=1,size+': switching to empty search result keeps position');
  ok(await p.locator('[data-search]').inputValue()==='no matching title',size+': filtering keeps search input');
  await p.locator('[data-search]').fill('application');ok(await p.locator('.event-card:visible').count()===0,size+': search cannot reveal wrong-state cards');
  await p.locator('[data-event-filter=ENTRIES]').click();ok(await p.locator('.event-card:visible').count()===1,size+': search and status work together');
  await p.locator('[data-search]').fill('');await p.locator('[data-event-filter=OPEN]').click();
 }
 await p.goto(base+'/my-votes');await p.locator('[data-event-filter=CLOSED]').click();ok(await p.locator('[data-empty-events]').isVisible(),'empty personal list filters correctly');
 const nojs=await browser.newContext({javaScriptEnabled:false});await nojs.addCookies(Object.entries(fixture.owner).map(([name,value])=>({name,value,url:base})));const np=await nojs.newPage();await np.goto(base+'/?status=OPEN');await np.locator('[data-event-filter=ENTRIES]').click();await np.waitForURL('**/?status=ENTRIES');ok(await np.locator('.event-card:visible').count()===1,'ordinary links still work without JavaScript');await nojs.close();
 ok(errors.length===0,'no JavaScript errors');fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(checks,null,2));console.log(JSON.stringify({passed:checks.length,output:out,checks},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server.exitCode===null)server.kill();fs.closeSync(log);});

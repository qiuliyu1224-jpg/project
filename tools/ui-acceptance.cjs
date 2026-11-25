/* Real browser acceptance with private disposable data and optional recording. */
const fs=require('node:fs'),path=require('node:path'),{spawn,spawnSync}=require('node:child_process');
const repo=path.resolve(__dirname,'..');
process.env.PLAYWRIGHT_BROWSERS_PATH??=path.join(repo,'node_modules/.cache/ms-playwright');
const {chromium}=require('playwright');
const out=path.join(repo,'test-results','ui-'+Date.now());fs.mkdirSync(out,{recursive:true});
const fixtureDir=path.join(out,'data');
const py=process.env.VOTELAB_PYTHON||(process.platform==='win32'?'python':'python3');
const log=fs.openSync(path.join(out,'server.log'),'w');
const server=spawn(py,['-u',path.join(__dirname,'ui-fixture.py'),fixtureDir],{cwd:repo,env:process.env,stdio:['ignore',log,log],windowsHide:true});
const checks=[],errors=[];const ok=(condition,name)=>{if(!condition)throw Error(name);checks.push(name);};
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let browser;
(async()=>{
 let state;
 for(let n=0;n<200;n++){
   const file=path.join(fixtureDir,'running-instance.json');
   if(fs.existsSync(file)){state=JSON.parse(fs.readFileSync(file));break;}
   if(server.exitCode!==null)throw Error(fs.readFileSync(path.join(out,'server.log'),'utf8'));
   await wait(100);
 }
 if(!state)throw Error('Fixture did not become ready');
 const fixture=JSON.parse(fs.readFileSync(path.join(fixtureDir,'fixture.json'))),base='http://127.0.0.1:'+state.port;
 browser=await chromium.launch({headless:true});
 const ownerContext=await browser.newContext({viewport:{width:1536,height:1000}});
 const voterContext=await browser.newContext({viewport:{width:1440,height:1000},recordVideo:{dir:path.join(out,'video'),size:{width:1440,height:1000}}});
 const cookies=(context,values)=>context.addCookies(Object.entries(values).map(([name,value])=>({name,value,url:base})));
 await cookies(ownerContext,fixture.owner);await cookies(voterContext,fixture.voter);
 const owner=await ownerContext.newPage(),p=await voterContext.newPage();
 for(const page of [owner,p]){page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());}
 await owner.goto(base+'/?lang=en&local='+state.token);await owner.waitForLoadState('networkidle');
 ok((await owner.locator('.brand').innerText()).includes('0.4.10'),'exact version visible');
 ok((await owner.locator('.hero h2').innerText()).includes('See the entry'),'original main slogan retained');
 ok(await owner.locator('.example-card').count()===3,'three general-purpose activity examples');
 ok(await owner.locator('.example-card>img').evaluateAll(images=>images.every(img=>img.complete&&img.naturalWidth>0)),'local cover assets load');
 await owner.screenshot({path:path.join(out,'01-home-en.png'),fullPage:true});
 await owner.locator('[name=lang]').selectOption('zh');await owner.waitForLoadState('networkidle');
 ok((await owner.locator('main').innerText()).includes('发现值得支持的想法'),'original Chinese heading retained');
 ok((await owner.locator('.example-grid').innerText()).includes('方案投票'),'original general activity categories retained');
 await owner.screenshot({path:path.join(out,'02-home-zh.png'),fullPage:true});
 await owner.goto(base+'/login');await owner.waitForLoadState('networkidle');
 ok(await owner.locator('.login-art').evaluate(img=>img.complete&&img.naturalWidth>0),'login illustration loads locally');
 await owner.screenshot({path:path.join(out,'03-login-zh.png'),fullPage:true});
 await owner.locator('[name=lang]').selectOption('en');await owner.waitForLoadState('networkidle');
 await p.goto(base+'/');await p.locator('.guide-open').click();await p.getByRole('button',{name:'I want to vote',exact:true}).click();
 for(let n=0;n<4;n++){ok(await p.locator('[data-tour-next]').isEnabled(),'voter explanation '+(n+1)+' is freely readable');await p.locator('[data-tour-next]').click();}
 await p.locator('[data-tour-finish]').click();
 ok(await p.locator('.ux-guide').count()===0,'voter guide finishes without casting a vote');
 await p.locator(`.event-card a[href="/e/${fixture.score}"]`).click();
 const first=p.locator('.stars').first();
 await first.locator('input[value="4"]').check({force:true});
 ok(await first.locator('.star-particle').count()===8,'star selection emits eight local particles');
 ok((await p.locator('.selected-note').first().innerText()).includes('4 / 5'),'rating value reflects selected score');
 await wait(700);ok(await p.locator('.star-particle').count()===0,'particles clean up after 600ms animation');

 await p.locator('[data-ballot] .sticky-actions button').click();await p.waitForURL(/\/confirm$/);

 let releaseRequest;const received=new Promise(resolve=>releaseRequest=resolve);
 await p.route(`**/e/${fixture.score}/status`,async route=>{await wait(350);await route.continue();});
 await p.route(`**/e/${fixture.score}/vote`,async route=>{releaseRequest();await wait(700);await route.continue();});
 const originalButton=await p.locator('[data-final-ballot] button').boundingBox();
 const click=p.locator('[data-final-ballot] button').click();
 await p.waitForSelector('.submit-spinner');ok(await p.locator('.submit-morph').isDisabled(),'click immediately starts loading before the status preflight finishes');
 await wait(90);const halfway=await p.locator('.submit-morph').boundingBox();
 ok(halfway.width<originalButton.width-3&&halfway.width>originalButton.height+2,'submit button visibly animates between full width and circle');
 await received;
 const circle=await p.locator('.submit-morph').boundingBox();ok(Math.abs(circle.width-circle.height)<2,'loading button finishes shrinking into a circle');
 ok(await p.locator('.submit-morph').isDisabled(),'submit button prevents duplicate clicks while saving');
 ok(await p.locator('.submit-spinner').count()===1,'real request shows circle loading state');
 await p.waitForSelector('.submit-morph.is-success');
 ok((await p.locator('[data-submit-status]').innerText()).includes('saved'),'checkmark waits for a successful server save');
 await p.screenshot({path:path.join(out,'04-submission-success.png'),fullPage:true});
 await click;await p.waitForURL(`${base}/e/${fixture.score}`);


 await p.screenshot({path:path.join(out,'05-rating-page.png'),fullPage:true});
 await p.goto(`${base}/e/${fixture.closing}`);await p.locator('[name=candidate]').first().check();await p.locator('[data-ballot] .sticky-actions button').click();await p.waitForURL(/\/confirm$/);
 await owner.goto(`${base}/e/${fixture.closing}`);await owner.getByRole('button',{name:'Close voting',exact:true}).click();await owner.waitForURL(`${base}/e/${fixture.closing}`);
 let blockedPosts=0;p.on('request',r=>{if(r.method()==='POST'&&r.url()===`${base}/e/${fixture.closing}/vote`)blockedPosts++;});
 await p.locator('[data-final-ballot] button').click();await p.waitForSelector('#ux-notice[open]');
 ok((await p.locator('#ux-notice p').innerText()).includes('has ended'),'ended event uses a small clear modal');
 ok(blockedPosts===0,'ended-event preflight does not post a ballot');
 ok(await p.locator('#ux-notice button').innerText()==='Got it','ended-event dialog has a simple acknowledgement');
 await p.screenshot({path:path.join(out,'06-ended-event-modal.png'),fullPage:true});await p.locator('#ux-notice button').click();
 await p.goto(`${base}/e/${fixture.failure}`);await p.locator('.stars').first().locator('input[value="0"]').check({force:true});await p.locator('[data-ballot] .sticky-actions button').click();await p.waitForURL(/\/confirm$/);
 await p.route(`**/e/${fixture.failure}/vote`,route=>route.fulfill({status:500,contentType:'text/html',body:'<div role="alert">A simulated save failure</div>'}));
 await p.locator('[data-final-ballot] button').click();await p.waitForSelector('#ux-notice[open]');
 ok((await p.locator('#ux-notice p').innerText()).includes('simulated save failure'),'failed save reports the error');
 ok(await p.locator('.submit-morph.is-success').count()===0,'failed save never shows a success check');
 ok(await p.locator('[data-final-ballot] button').isEnabled(),'failed save restores original button');
 await p.locator('#ux-notice button').click();await p.unroute(`**/e/${fixture.failure}/vote`);
 await p.locator('[data-final-ballot] button').click();await p.waitForURL(`${base}/e/${fixture.failure}`);
 ok((await p.locator('.notice.success').innerText()).includes('saved'),'retry after an explicit failure can save a zero rating');
 await owner.goto(base+'/');await owner.locator('.guide-open').click();await owner.getByRole('button',{name:'I want to create an event',exact:true}).click();
 await owner.locator('[data-tour-next]').click();await owner.locator('[data-tour-next]').click();
 ok(await owner.locator('[data-tour-finish]').isEnabled(),'creator can finish at the entry explanation without saving');
 await owner.locator('[data-tour-finish]').click();
 await owner.goto(base+'/create?template=custom');
 await owner.locator('[name=title]').fill('Guided test event');
 await owner.locator('[name=entry_name_0]').fill('Guided A');await owner.locator('[name=entry_name_1]').fill('Guided B');
 await owner.locator('[data-event-form] .sticky-actions button').click();await owner.waitForURL(/\/preview$/);
 ok((await owner.locator('main').innerText()).includes('Preview'),'real creator save still opens preview');
 await owner.locator('form[action$="/open"] button').click();await owner.waitForURL(/\/e\/\d+$/);
 ok(await owner.locator('[data-event-status][data-state="OPEN"]').count()>0,'real creator confirmation still opens voting');
 await p.setViewportSize({width:390,height:844});await p.goto(base+'/');await p.waitForLoadState('networkidle');
 ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile homepage does not overflow horizontally');
 await p.screenshot({path:path.join(out,'07-mobile-home.png'),fullPage:true});
 await p.goto(`${base}/e/${fixture.score}`);ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile rating page fits');
 await p.screenshot({path:path.join(out,'08-mobile-ratings.png'),fullPage:true});
 await p.locator('.guide-open').click();await p.getByRole('button',{name:'I want to vote',exact:true}).click();
 ok(await p.locator('.tour-close').isVisible(),'mobile guide remains closable');await p.locator('.tour-close').click();
 const quiet=await browser.newContext({reducedMotion:'reduce'});await cookies(quiet,fixture.other);const qp=await quiet.newPage();await qp.goto(`${base}/e/${fixture.score}`);await qp.locator('.stars').first().locator('input[value="5"]').check({force:true});
 ok(await qp.locator('.star-particle').count()===0,'reduced-motion preference suppresses particles');await quiet.close();
 ok(errors.length===0,'no browser JavaScript errors');
 await voterContext.close();await ownerContext.close();
 const video=fs.readdirSync(path.join(out,'video')).find(name=>name.endsWith('.webm'));
 if(video){const result=spawnSync(process.execPath,[path.join(__dirname,'encode-video.cjs'),path.join(out,'video',video),path.join(out,'walkthrough.mp4')],{encoding:'utf8'});ok(result.status===0,'project FFmpeg encodes a playable MP4');}
 fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(checks,null,2));
 console.log(JSON.stringify({passed:checks.length,output:out,checks},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
 if(browser)await browser.close();
 if(server.exitCode===null)server.kill();
 fs.closeSync(log);
 fs.writeFileSync(path.join(out,'checks-partial.json'),JSON.stringify({checks,errors},null,2));
});

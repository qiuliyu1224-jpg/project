const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const repo=path.resolve(__dirname,'..');process.env.PLAYWRIGHT_BROWSERS_PATH??=path.join(repo,'node_modules/.cache/ms-playwright');
const {chromium}=require('playwright'),out=path.join(repo,'test-results','accounts-'+Date.now());fs.mkdirSync(out,{recursive:true});
const data=path.join(out,'data'),py=process.env.VOTELAB_PYTHON||'python',log=fs.openSync(path.join(out,'server.log'),'w');
const server=spawn(py,['-u',path.join(__dirname,'ui-fixture.py'),data,'--empty'],{cwd:repo,env:process.env,stdio:['ignore',log,log],windowsHide:true});
const checks=[],ok=(v,n)=>{if(!v)throw Error(n);checks.push(n);};let browser;
(async()=>{
 let state;for(let i=0;i<200;i++){if(fs.existsSync(path.join(data,'running-instance.json'))){state=JSON.parse(fs.readFileSync(path.join(data,'running-instance.json')));break;}if(server.exitCode!==null)throw Error(fs.readFileSync(path.join(out,'server.log'),'utf8'));await new Promise(r=>setTimeout(r,100));}if(!state)throw Error('No server');
 const base='http://127.0.0.1:'+state.port;browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000}}),p=await context.newPage();
 await p.goto(base+'/login');ok(await p.locator('html').getAttribute('lang')==='en','fresh default English');
 async function login(phone){const f=p.locator('form[action="/login"]');await f.locator('[name=phone]').fill(phone);await f.locator('[name=password]').fill('Test-only-pass123');await f.locator('[name=remember]').check();await f.locator('button.full-width').click();await p.waitForURL(base+'/');}
 await login('80000001');ok(await p.locator('.local-scope').isVisible(),'local scope visible');
 await p.locator('form[action="/switch-account"] button').click();await p.waitForURL('**/accounts');ok(await p.locator('.account-row').getByText('Test organiser',{exact:true}).isVisible(),'current remembered account shown');
 await p.locator('form[action="/accounts/login"] button').click();await p.waitForURL('**/login');await login('80000002');
 await p.locator('form[action="/switch-account"] button').click();await p.waitForURL('**/accounts');ok(await p.locator('.account-row').count()===2,'two saved accounts');await p.screenshot({path:path.join(out,'accounts-en.png'),fullPage:true});
 await p.locator('form[action="/accounts/select"] button').click();await p.waitForURL(base+'/');ok((await p.locator('.sidebar').innerText()).includes('Test organiser'),'switch completes');
 await p.goto(base+'/create');await p.locator('[name=method]').selectOption('MAJORITY');const help=p.locator('.rule-help').first();await help.locator('summary').click();ok(await help.locator('p').isVisible(),'click opens majority rules');ok((await help.innerText()).includes('50%'),'absolute majority threshold');await help.locator('summary').click();ok(!(await help.locator('p').isVisible()),'click closes rule explanation');
 await p.locator('.rule-help').nth(1).locator('summary').click();ok((await p.locator('.rule-help').nth(1).innerText()).includes('tie'),'RCV tie boundary explained');await p.screenshot({path:path.join(out,'rules-en.png'),fullPage:true});
 await p.locator('[name=lang]').selectOption('zh');await p.waitForLoadState('networkidle');ok(await p.locator('html').getAttribute('lang')==='zh-CN','workspace switches language');
 await p.locator('form[action="/switch-account"] button').click();await p.waitForURL('**/accounts');ok(await p.getByText('切换账号',{exact:true}).count()>0,'account picker Chinese');await p.screenshot({path:path.join(out,'accounts-zh.png'),fullPage:true});
 await p.setViewportSize({width:390,height:844});ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile no horizontal overflow');
 console.log(JSON.stringify({passed:checks.length,output:out,checks}));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server.exitCode===null)server.kill();fs.closeSync(log);});


/* Local, bilingual guidance and feedback. No automatic votes or external requests. */
(() => {
  'use strict';
  const zh=document.documentElement.lang.startsWith('zh');
  const t=(a,b)=>zh?a:b;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,reduced?0:ms));
  const query=s=>document.querySelector(s);
  const key='votelab-guide-v1';
  const read=()=>{try{return JSON.parse(sessionStorage.getItem(key)||'null');}catch(_){return null;}};
  const save=value=>{try{value?sessionStorage.setItem(key,JSON.stringify(value)):sessionStorage.removeItem(key);}catch(_){/* Guidance still works without browser storage. */}};
  let tour=read(),panel=null,highlight=null,origin=null;
  if(!tour||!['creator','voter'].includes(tour.role)||!Number.isInteger(tour.step)||tour.step<0||tour.step>4)tour=null;
  if(tour&&!['photo','choice','custom'].includes(tour.template))tour.template='custom';

  function notice(message,uncertain=false){
    let dialog=query('#ux-notice');
    if(!dialog){
      dialog=document.createElement('dialog');dialog.id='ux-notice';dialog.className='ux-dialog';
      dialog.setAttribute('aria-labelledby','ux-notice-title');
      dialog.innerHTML='<h2 id="ux-notice-title"></h2><p></p><div class="button-row"><button class="btn" type="button"></button><a class="btn secondary" href="/my-votes" hidden></a></div>';
      dialog.querySelector('button').addEventListener('click',()=>dialog.close());document.body.append(dialog);
    }
    dialog.querySelector('h2').textContent=t('提示','Notice');
    dialog.querySelector('p').textContent=message;
    dialog.querySelector('button').textContent=t('知道了','Got it');
    const votes=dialog.querySelector('a');votes.hidden=!uncertain;votes.textContent=t('查看我的投票','Check My votes');
    if(!dialog.open)dialog.showModal();
  }
  window.VoteLabNotice=notice;

  // The selected score rolls; the vote count changes only after a saved ballot.
  document.querySelectorAll('.stars').forEach(stars=>stars.addEventListener('change',event=>{
    const input=event.target;
    if(input.tagName!=='INPUT'||!input.checked||input.disabled)return;
    const label=input.closest('.star-choice');
    const note=stars.parentElement.querySelector('.selected-note');
    if(note){note.setAttribute('aria-live','polite');note.replaceChildren();const value=document.createElement('span');value.className='score-roll';value.textContent=input.value+' / 5 · '+t('已评分','Rated');note.append(value);}
    if(reduced||input.value==='0')return;
    label.classList.remove('is-burst');void label.offsetWidth;label.classList.add('is-burst');
    label.querySelectorAll('.star-particle').forEach(p=>p.remove());
    for(let i=0;i<8;i++){
      const p=document.createElement('i');p.className='star-particle';p.setAttribute('aria-hidden','true');
      const angle=i*Math.PI/4;p.style.setProperty('--dx',Math.cos(angle)*29+'px');p.style.setProperty('--dy',Math.sin(angle)*27+'px');
      label.append(p);setTimeout(()=>p.remove(),650);
    }
    setTimeout(()=>label.classList.remove('is-burst'),650);
  }));

  async function checkBallotState(form){
    const eid=form.action.match(/\/e\/(\d+)\//)?.[1];
    if(!eid)return null;
    const response=await fetch('/e/'+eid+'/status',{cache:'no-store',credentials:'same-origin',signal:AbortSignal.timeout(8000)});
    if(!response.ok)return null; // The authoritative POST still checks access/session.
    const current=await response.json();
    if(current.status==='CLOSED')return t('活动已结束，无法继续投票。','This event has ended. Voting is closed.');
    if(current.status!=='OPEN')return t('活动尚未开始，暂时不能投票。','Voting has not started yet.');
    if(current.paused)return t('活动已暂停，请稍后再试。','Voting is paused. Please try again later.');
    if(form.dataset.roundNumber&&String(current.round)!==form.dataset.roundNumber)return t('活动已进入新轮次，请返回活动重新选择。','A new round has started. Return to the event and choose again.');
    return null;
  }

  const ballot=query('[data-ballot]');
  if(ballot){
    ballot.addEventListener('submit',async event=>{
      if(event.defaultPrevented)return;
      event.preventDefault();
      const button=ballot.querySelector('button:not([type="button"])');
      if(ballot.dataset.checking)return;ballot.dataset.checking='1';
      try{
        const message=await checkBallotState(ballot);
        if(message){notice(message);return;}
        // Native submission keeps progressive enhancement and existing validation.
        HTMLFormElement.prototype.submit.call(ballot);
      }catch(_){notice(t('暂时无法核对活动状态，请稍后再试。你的选择已保留。','The event status could not be checked. Try again shortly. Your choices are kept.'));}
      finally{delete ballot.dataset.checking;}
    });
  }

  const final=query('[data-final-ballot]');
  if(final){
    const button=final.querySelector('button');
    button.classList.add('submit-morph');
    final.addEventListener('submit',async event=>{
      event.preventDefault();if(button.disabled)return;
      const original=button.innerHTML,width=button.getBoundingClientRect().width,height=button.getBoundingClientRect().height;
      const status=final.querySelector('[data-submit-status]');
      const fields=new URLSearchParams(new FormData(final));
      button.disabled=true;button.setAttribute('aria-busy','true');
      button.style.width=width+'px';button.style.height=height+'px';
      // Establish a numeric starting width so auto -> circle animates for 300ms.
      void button.offsetWidth;
      const restore=()=>{button.classList.remove('is-loading','is-success');button.classList.add('is-restored');button.style.width=width+'px';button.innerHTML=original;button.disabled=false;button.removeAttribute('aria-busy');button.removeAttribute('aria-label');};
      status.textContent=t('正在提交，请稍候…','Saving your ballot…');
      button.classList.add('is-loading');button.setAttribute('aria-label',t('正在提交','Saving ballot'));
      button.style.width=height+'px';button.innerHTML='<span class="submit-spinner" aria-hidden="true"></span>';
      try{
        const message=await checkBallotState(final);
        if(message){restore();status.textContent='';notice(message);return;}
        const start=performance.now();
        const response=await fetch(final.action,{method:'POST',body:fields,credentials:'same-origin',signal:AbortSignal.timeout(20000)});
        const html=await response.text();
        const doc=new DOMParser().parseFromString(html,'text/html');
        const destination=new URL(response.url,location.href);
        const saved=response.ok&&response.redirected&&destination.origin===location.origin&&/\/e\/\d+$/.test(destination.pathname)&&doc.querySelector('.notice.success');
        if(!saved){
          const error=doc.querySelector('[role="alert"]')?.textContent.trim();
          restore();status.textContent='';button.removeAttribute('aria-label');
          const closed=response.status===409&&/closed|截止|结束/i.test(error||'');
          notice(closed?t('活动已结束或已暂停，无法继续投票。','Voting has ended or is paused.'):error||t('尚未确认保存，请先查看我的投票。','Saving could not be confirmed. Check My votes first.'),!error);
          return;
        }
        // A fast response still shows the full 300ms shrink; success is never faked.
        await pause(Math.max(0,300-(performance.now()-start)));
        button.classList.remove('is-loading');button.classList.add('is-success');
        button.setAttribute('aria-label',t('选票已保存','Ballot saved'));
        button.innerHTML='<svg class="submit-tick" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L20 5"/></svg>';
        status.textContent=t('选票已成功保存。','Your ballot has been saved.');
        await pause(650);button.classList.remove('is-success');button.style.width=width+'px';button.innerHTML=original;
        await pause(300);location.assign(destination.href);
      }catch(_){
        restore();button.removeAttribute('aria-label');status.textContent='';
        notice(t('无法确认提交结果，请先查看我的投票，避免重复提交。','The submission result could not be confirmed. Check My votes before trying again.'),true);
      }
    });
  }

  function clearTarget(){if(highlight)highlight.classList.remove('tour-target');highlight=null;}
  function closeTour(){save(null);tour=null;clearTarget();panel?.remove();panel=null;if(origin?.isConnected)origin.focus();}
  function ensurePanel(){
    if(panel)return;
    panel=document.createElement('section');panel.className='ux-guide';panel.setAttribute('role','region');panel.setAttribute('aria-label',t('5步操作指南','5-step guide'));document.body.append(panel);
  }
  function focusTarget(selector,scroll=false){
    clearTarget();if(!selector)return;
    const targets=[...document.querySelectorAll(selector)];highlight=targets.find(el=>el.getClientRects().length);
    if(!highlight)return;highlight.classList.add('tour-target');
    if(scroll)highlight.scrollIntoView({behavior:reduced?'instant':'smooth',block:'center'});
  }
  function go(path){save(tour);location.assign(path);}
  function chooseRole(){
    clearTarget();ensurePanel();panel.classList.remove('guide-at-top');
    panel.innerHTML='<header><span>'+t('VOTELAB · 操作指南','VOTELAB · QUICK GUIDE')+'</span><button type="button" class="tour-close" aria-label="'+t('关闭指南','Close guide')+'">×</button></header><h2 tabindex="-1">'+t('你想做什么？','What would you like to do?')+'</h2><p>'+t('选一个目标，跟着5步找到实际按钮。随时可以关闭或重新开始。','Choose a goal. Five steps point to real controls. You can close or restart at any time.')+'</p><div class="tour-role"><button type="button" class="btn" data-role="voter">'+t('我要参与投票','I want to vote')+'</button><button type="button" class="btn secondary" data-role="creator">'+t('我要创建活动','I want to create an event')+'</button></div>';
    panel.querySelector('.tour-close').onclick=closeTour;
    panel.querySelectorAll('[data-role]').forEach(button=>button.onclick=()=>{tour={role:button.dataset.role,step:0,template:'custom'};save(tour);renderTour(true);});
    panel.querySelector('h2').focus();
  }
  function renderTour(scroll=false){
    if(!tour)return;
    ensurePanel();
    const authenticated=document.body.dataset.authenticated==='1';
    const eventPath=/^\/e\/\d+(?:\/preview)?$/.test(location.pathname);
    const isConfirm=!!final,saved=!!query('.notice.success'),open=!!query('[data-event-status][data-state="OPEN"]');
    if(tour.role==='voter'&&tour.step===1&&(eventPath||isConfirm))tour.step=2;
    if(tour.role==='voter'&&tour.step===3&&saved)tour.step=4;
    if(tour.role==='creator'&&tour.step===2&&location.pathname.endsWith('/preview'))tour.step=3;
    if(tour.role==='creator'&&tour.step===3&&eventPath&&open)tour.step=4;
    save(tour);
    let title='',body='',target='',action=null,label=t('下一步','Next'),disabled=false;
    const next=()=>{tour.step=Math.min(4,tour.step+1);save(tour);renderTour(true);};
    action=next;
    if(tour.step===0){
      title=t('登录你的账号','Sign in to your account');
      body=authenticated?t('你已登录。一个账号可以创建活动、提交作品和投票。','You are signed in. One account can create, submit entries and vote.'):t('先注册或登录。课程演示验证码会显示在页面，不会发送短信。','Register or log in first. Demo codes appear on screen; no SMS is sent.');
      target=authenticated?'.brand':'form[action="/login"],form[action="/register"],a[href="/login"]';
      if(!authenticated){label=t('打开登录页','Open login');action=()=>go('/login');}
    }else if(tour.role==='voter'){
      if(tour.step===1){title=t('找到要参加的活动','Find your event');body=t('在活动广场搜索名称或编号，再打开一场投票中的活动。需要邀请码时，向发起者获取。','Search Explore by title or event code, then open an event with voting open. Ask the organiser for any required invitation code.');target='.toolbar,.grid';label=t('定位活动列表','Show event list');action=()=>location.pathname==='/'?focusTarget('.toolbar,.grid',true):go('/');}
      if(tour.step===2){
        title=t('选择、评分或排序','Choose, rate or rank');body=t('按活动规则操作。星级评分可用0分；未评分不等于0分。这里只选择，还没有保存选票。','Follow the event rules. Zero is a valid rating; skipping is different. Choosing here does not save a ballot.');target='[data-ballot] .candidate-grid';
        const form=query('[data-ballot]');const method=form?.dataset.method;
        disabled=!form||!form.querySelector('input[name="candidate"]:checked,input[name^="score_"]:checked,select[name^="rank_"] option:checked:not([value=""])');
        if(isConfirm){disabled=false;target='[data-final-ballot]';}
      }
      if(tour.step===3){title=t('核对，再确认提交','Review, then confirm');body=isConfirm?t('检查这页的选择，再点击“确认提交”。指南不会替你投票。','Check this summary, then use Confirm and submit. The guide never votes for you.'):t('点击页面上的“核对选票”，检查后再确认提交。核对页面本身不会计票。','Use Review ballot on the page, check the summary, then confirm. Reviewing alone saves no vote.');target=isConfirm?'[data-final-ballot] button':'[data-ballot] .sticky-actions';label=t('定位操作按钮','Show the button');action=()=>focusTarget(target,true);}
      if(tour.step===4){title=t('确认保存与查看结果','Check your saved ballot');body=t('看到“投票已成功保存”才算完成。可以在“我的投票”找回活动；结束且结果可见时再查看统计。','The saved-ballot message confirms completion. Find the event in My votes; view results after voting closes when access permits.');target='.notice.success,a[href="/my-votes"]';label=t('完成指南','Finish guide');action=closeTour;}
    }else{
      if(tour.step===1){title=t('设置活动规则','Set the event rules');body=t('填写名称，选择投票方式、截止时间与结果权限。截止时间按北京时间UTC+8。','Enter a title, choose the voting method, deadline and result visibility. Deadlines use Beijing time, UTC+8.');target='[data-event-form]';if(!query('[data-event-form]')){label=t('打开创建页面','Open event builder');action=()=>go('/create?template='+tour.template);}}
      if(tour.step===2){title=t('添加作品并保存预览','Add entries and preview');body=t('填写作品名称，图片可选。点击页面的“保存并预览”。若开放报名，开票前需至少2项通过且没有待审核作品。','Add entry names and optional images, then use Save and preview. Application events need at least two approved entries and no pending reviews before voting.');target='[data-entry-list],[data-event-form] .sticky-actions';label=t('定位保存按钮','Show save button');action=()=>focusTarget('[data-event-form] .sticky-actions',true);}
      if(tour.step===3){title=t('检查后开始投票','Check and open voting');body=t('核对预览。需要报名时先开放报名并审核；准备好后点击“确认设置并开始投票”。指南不会自动开票。','Check the preview. Open applications and review entries if needed, then use Confirm settings and start voting. The guide does not open voting automatically.');target='form[action$="/open"],a[href$="/review"]';label=t('定位开始按钮','Show start button');action=()=>focusTarget(target,true);}
      if(tour.step===4){title=t('管理活动与查看结果','Manage the event and results');body=t('活动已开启，可在“我的活动”找回。投票结束后查看结果、导出图表；遇平票可按提示发起加赛。','Voting is open. Find it in My events. After voting ends, view results, export charts or explicitly start a revote for unresolved ties.');target='.rule-panel,a[href="/dashboard"]';label=t('完成指南','Finish guide');action=closeTour;}
    }
    panel.classList.toggle('guide-at-top',tour.step===3);
    panel.innerHTML='<header><span>'+t(tour.role==='voter'?'参与投票':'创建活动',tour.role==='voter'?'VOTE':'CREATE AN EVENT')+' · '+(tour.step+1)+' / 5</span><button type="button" class="tour-close" aria-label="'+t('关闭指南','Close guide')+'">×</button></header><div class="tour-progress" aria-hidden="true">'+[0,1,2,3,4].map(i=>'<span class="'+(i<=tour.step?'filled':'')+'"></span>').join('')+'</div><h2 tabindex="-1">'+title+'</h2><p>'+body+'</p><footer><button class="text-button" data-tour-restart type="button">'+t('重新选择','Change goal')+'</button>'+(tour.step?'<button class="btn secondary" data-tour-back type="button">'+t('上一步','Back')+'</button>':'')+'<button class="btn" data-tour-next type="button" '+(disabled?'disabled':'')+'>'+label+'</button></footer>';
    panel.querySelector('.tour-close').onclick=closeTour;
    panel.querySelector('[data-tour-restart]').onclick=()=>{save(null);tour=null;chooseRole();};
    panel.querySelector('[data-tour-back]')?.addEventListener('click',()=>{tour.step--;save(tour);renderTour(true);});
    panel.querySelector('[data-tour-next]').onclick=action;
    focusTarget(target,scroll);if(scroll)panel.querySelector('h2').focus({preventScroll:true});
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-guide-open]');if(!button)return;
    origin=button;
    if(button.dataset.guideRole){tour={role:button.dataset.guideRole,step:0,template:button.dataset.guideTemplate||'custom'};save(tour);renderTour(true);}else chooseRole();
  });
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&panel&&!query('#ux-notice[open]'))closeTour();});
  document.addEventListener('change',event=>{if(tour&&tour.step===2&&event.target.closest('[data-ballot]'))renderTour();});
  if(tour)renderTour();
})();

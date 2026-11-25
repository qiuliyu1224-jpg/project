/* Local, bilingual guidance and feedback. No automatic votes or external requests. */
(() => {
  'use strict';
  const zh=document.documentElement.lang.startsWith('zh');
  const t=(a,b)=>zh?a:b;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,reduced?0:ms));
  const query=s=>document.querySelector(s);

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

})();

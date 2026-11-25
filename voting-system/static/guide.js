/* Read-through guides and in-memory practice. Never submit a real form. */
(() => {
  'use strict';
  const zh=document.documentElement.lang.startsWith('zh'),t=(a,b)=>zh?a:b;
  const $=s=>document.querySelector(s),key='votelab-guide-v2';
  const learningHost=()=>document.querySelector('dialog[data-learning-dialog][open]');
  const roles={voter:t('我要投票','I want to vote'),creator:t('我要创建活动','I want to create an event'),entrant:t('我要报名提交作品','I want to submit an entry')};
  let guide=null,panel=null,target=null,origin=null,practice=null;
  try{guide=JSON.parse(sessionStorage.getItem(key)||'null');}catch(_){}
  if(!guide||!roles[guide.role]||!Number.isInteger(guide.step)||guide.step<0||guide.step>4)guide=null;
  function remember(){try{guide&&!learningHost()?.classList.contains('vote-demo')?sessionStorage.setItem(key,JSON.stringify(guide)):sessionStorage.removeItem(key);}catch(_){}}
  function clearTarget(){target?.classList.remove('tour-target');target=null;}
  function close(){guide=null;remember();clearTarget();panel?.remove();panel=null;if(origin?.isConnected)origin.focus({preventScroll:true});}
  function highlight(selector,scroll=false){
    clearTarget();if(!selector)return;
    target=[...document.querySelectorAll(selector)].find(el=>el.getClientRects().length);
    if(!target)return;target.classList.add('tour-target');
    if(scroll)target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'center'});
  }
  function shell(){
    if(!panel){panel=document.createElement('section');panel.className='ux-guide';panel.setAttribute('role','region');panel.setAttribute('aria-label',t('操作指南','Quick guide'));}
    const host=learningHost()||document.body;if(panel.parentElement!==host)host.append(panel);
    panel.innerHTML='<header><span>'+t('VOTELAB · 操作指南','VOTELAB · QUICK GUIDE')+'</span><button type="button" class="tour-close" aria-label="'+t('关闭指南','Close guide')+'">×</button></header>';
    panel.querySelector('.tour-close').onclick=close;
  }
  function choose(){
    guide=null;remember();clearTarget();shell();
    panel.insertAdjacentHTML('beforeend','<h2 tabindex="-1">'+t('你想了解什么？','What would you like to learn?')+'</h2><p>'+t('每条指南只有5步。可以只看说明，随时跳过或结束，不用填写、保存或提交。','Five short steps. Read without filling, saving or submitting anything. Skip or finish whenever you like.')+'</p><div class="tour-role">'+Object.entries(roles).map(([r,label])=>'<button class="btn secondary" type="button" data-role="'+r+'">'+label+'</button>').join('')+'</div><div class="guide-practice-links"><span>'+t('没有活动？先试一遍：','No events yet? Try a practice:')+'</span><button type="button" class="text-button" data-demo="voter">'+t('演示投票','Practice voting')+'</button><button type="button" class="text-button" data-demo="entrant">'+t('演示报名','Practice entry submission')+'</button></div>');
    panel.querySelectorAll('[data-role]').forEach(b=>b.onclick=()=>{guide={role:b.dataset.role,step:0};remember();render();});
    panel.querySelectorAll('[data-demo]').forEach(b=>b.onclick=()=>demo(b.dataset.demo));panel.querySelector('h2').focus({preventScroll:true});
  }
  function steps(role){
    if(role==='voter'&&learningHost()?.classList.contains('vote-demo'))return [
      [t('这是演示，不是正式活动','A demo, separate from real events'),t('可自由体验评分、核对和提交。记录只在当前窗口里；刷新、关闭或重新体验会清空。阅读指南不必实际操作。','Try rating, review and submission. Demo records stay in this window and clear on refresh, close or restart. Reading this guide never requires taking those actions.'),'.demo-scope'],
      [t('先看作品，再做选择','Explore the entries first'),t('三件作品各有图片和介绍，点击图片可以放大。按关闭或Esc返回作品，不影响已经选择的评分。','Read the descriptions and enlarge any of the three images. Close the image or press Escape to return without losing ratings.'),'[data-demo-entries]'],
      [t('评分可以为零，也可以跳过','Zero and skipping are different'),t('每件作品可评0～5分，至少评一件才可提交演示。清除后为未评分，不算0分。你仍可直接结束指南。','Rate entries from 0 to 5. Rate at least one to submit the demo. Clear means not rated, not zero. You can still finish this guide immediately.'),'.demo-score-group'],
      [t('核对后再提交演示选票','Review before demo submission'),t('点击核对，确认各项评分；想修改时返回编辑。提交演示选票只更新本窗口，不进入正式活动。','Review each rating, or go back to edit. Submitting a demo ballot updates only this window and never a real event.'),'.demo-actions'],
      [t('查看本次评分，随时重新体验','See your ratings or try again'),t('演示结果只有你本次的评分，没有预置票数。可重新体验，或退出回原页面；正式投票仍须在实际活动中确认。','Results contain only this demo ballot, with no preset votes. Restart or return to the previous page. Real voting still requires confirmation in a real event.'),'.demo-actions']
    ];
    const login=[t('一个账号，三种使用目标','One account, three ways to take part'),t('登录后可以投票、创建活动或报名提交作品，不需要另建不同身份的账号。登录和注册页、主界面都可以切换语言。','One account can vote, create events and submit entries. Language switching is available on sign-in, registration and the main screen.'),document.body.dataset.authenticated==='1'?'.brand':'form[action="/login"],form[action="/register"]'];
    const find=[t(role==='entrant'?'找到报名中的活动':'找到投票中的活动',role==='entrant'?'Find an event accepting entries':'Find an event with voting open'),t('在活动广场按名称或编号搜索，并查看状态和截止时间。有邀请码时，向发起者获取。每台电脑的数据独立，邀请码不会同步其他电脑上的活动。','Search Explore by title or code and check its status and deadline. Ask the organiser for any invitation code. Each computer has separate data; invitation codes do not sync events between computers.'),'.toolbar,.grid'];
    if(role==='voter')return [login,find,
      [t('选择、评分或排序','Choose, rate or rank'),t('按活动规则选择。星级评分中0分有效，未评分不当作0分；排序可以只排部分作品。此时还没有保存选票。','Follow the event rules. Zero is a valid rating; skipping is different from zero. Ranking may be partial. Selections alone do not save a ballot.'),'[data-ballot] .candidate-grid'],
      [t('核对后，由你确认提交','Review and confirm when ready'),t('准备好时点击“核对选票”，检查后再“确认提交”。这是实际投票操作；看指南不需要提交。活动结束或暂停时不能投票。','When ready, use Review ballot, then Confirm and submit. These are real voting actions, not requirements for reading this guide. Closed or paused events cannot accept votes.'),'[data-final-ballot],[data-ballot] .sticky-actions'],
      [t('保存记录与查看结果','Saved ballots and results'),t('真正提交成功后会显示保存提示，可从“我的投票”找回活动。结果何时可见取决于活动结束、发布状态和权限。你现在也可以直接结束指南。','A real successful submission shows a saved message. Find the event in My votes. Results depend on closure, publication and access permissions. You can finish this guide now.'),'a[href="/my-votes"]']];
    if(role==='entrant')return [login,find,
      [t('填写作品与添加图片','Describe your entry'),t('查看报名要求和截止时间，再填写作品名称、介绍，图片可选，支持JPEG、PNG、WebP，单张最多5MB。现在只了解流程，不用真的填写。','Check the requirements and deadline, then add a title, description and optional JPEG, PNG or WebP image, up to 5 MB. You can read this step without filling anything in.'),'[data-entry-application]'],
      [t('提交后等待审核','Submission waits for review'),t('核对后可点击“提交审核”。实际提交后状态为“待审核”，不代表已经通过；活动停止报名或截止后不能再提交。','When ready, check your entry and choose Submit for review. A submitted entry is pending, not approved. Submissions are unavailable after applications close or the deadline passes.'),'[data-entry-application] button'],
      [t('从“我的作品”查看审核','Check My entries'),t('在“我的作品”查看待审核、已通过或已驳回及原因。被驳回后，报名仍开放且未截止时可修改重交；已经通过或待审核的作品不能按此入口重交。','My entries shows Pending, Approved or Rejected with feedback. A rejected entry can be edited and resubmitted while applications remain open and before the deadline. Pending or approved entries cannot be resubmitted through that action.'),'a[href="/my-entries"]']];
    return [login,
      [t('设置活动规则','Set the event rules'),t('选择模板或自定义，填写名称、投票方式、截止时间、结果权限和可选邀请码。截止时间按北京时间UTC+8。','Choose a template or customise it. Set the title, voting method, deadline, result visibility and optional invitation code. Deadlines use Beijing time, UTC+8.'),'[data-event-form]'],
      [t('添加作品，了解预览入口','Add entries and find the preview'),t('填写作品名称，图片可选。“保存并预览”会真正创建或保存活动，准备好时再操作。看到这里已经了解主要填写方法，可以直接结束指南。','Entry names are required; images are optional. Save and preview really creates or saves an event, so use it when ready. You now know the main editing steps and may finish this guide here.'),'[data-entry-list],[data-event-form] .sticky-actions'],
      [t('了解审核与开始投票','Review entries and open voting'),t('预览后可确认开始投票。报名活动需先开放报名并审核，至少2项通过且没有待审核作品才能开票。开票需要你实际确认，看指南不要求开票。','After previewing, the creator can open voting. Application events require at least two approved entries and no pending entries. Opening voting requires your actual confirmation; this guide does not require it.'),'form[action$="/open"],a[href$="/review"]'],
      [t('管理活动与结果','Manage events and results'),t('从“我的活动”找回活动。结束后按权限查看结果、导出图表；平票等未决结果可按提示开启新轮次，历史选票保留。','Find your events in My events. After closure, view permitted results and export charts. Unresolved ties may use an explicit new round while historical ballots are retained.'),'a[href="/dashboard"]']];
  }
  function render(){
    if(!guide)return;remember();shell();const [title,body,selector]=steps(guide.role)[guide.step];
    panel.insertAdjacentHTML('beforeend','<div class="tour-progress" aria-hidden="true">'+[0,1,2,3,4].map(n=>'<span class="'+(n<=guide.step?'filled':'')+'"></span>').join('')+'</div><small>'+roles[guide.role]+' · '+(guide.step+1)+' / 5</small><h2 tabindex="-1">'+title+'</h2><p>'+body+'</p><div class="guide-context"></div><footer><button class="text-button" type="button" data-tour-restart>'+t('重新选择','Change goal')+'</button>'+(guide.step?'<button class="btn secondary" type="button" data-tour-back>'+t('上一步','Back')+'</button>':'')+(guide.step<4?'<button class="btn secondary" type="button" data-tour-next>'+t('下一步说明','Next explanation')+'</button>':'')+'<button class="btn" type="button" data-tour-finish>'+t('了解了，结束指南','Got it, finish guide')+'</button></footer>');
    const context=panel.querySelector('.guide-context');
    if(selector&&[...document.querySelectorAll(selector)].some(el=>el.getClientRects().length))context.innerHTML='<button class="text-button" type="button" data-tour-locate>'+t('在当前页面看看位置','Show its location on this page')+'</button>';
    if(guide.step===1&&guide.role!=='creator'&&!learningHost()?.classList.contains('vote-demo')){
      const availability=$('[data-event-availability]'),field=guide.role==='voter'?'votingCount':'applicationCount';
      if(availability&&availability.dataset[field]==='0')context.insertAdjacentHTML('beforeend','<p class="guide-empty-note">'+t(guide.role==='voter'?'目前没有可投票活动，可以先体验演示。':'目前没有可报名活动，可以先体验演示。',guide.role==='voter'?'No events are open for voting. You can practise first.':'No events are accepting entries. You can practise first.')+'</p>');
      context.insertAdjacentHTML('beforeend','<button class="text-button" type="button" data-guide-demo>'+t('体验演示（不保存真实记录）','Try a practice (no real records)')+'</button>');
      context.querySelector('[data-guide-demo]').onclick=()=>demo(guide.role);
    }
    if(guide.role==='creator'&&guide.step===1&&!/^\/create|\/e\/\d+\/(edit|revision)/.test(location.pathname)){
      const template=['photo','choice','custom'].includes(guide.template)?guide.template:'custom';
      context.insertAdjacentHTML('beforeend','<p>'+t('下面只打开填写页；你保存后才会创建正式活动。','This opens the editor. A real event is created only when you save.')+'</p><a class="btn secondary" href="/create?template='+template+'">'+t('去创建活动','Go to create an event')+' →</a>');
    }
    panel.querySelector('[data-tour-restart]').onclick=choose;
    panel.querySelector('[data-tour-finish]').onclick=close;
    panel.querySelector('[data-tour-back]')?.addEventListener('click',()=>{guide.step--;render();});
    panel.querySelector('[data-tour-next]')?.addEventListener('click',()=>{guide.step++;render();});
    panel.querySelector('[data-tour-locate]')?.addEventListener('click',()=>highlight(selector,true));
    clearTarget();panel.querySelector('h2').focus({preventScroll:true});
  }

  // Practice lives only in this dialog's JS memory. No form action, fetch or storage.
  function demo(role){
    if(role==='voter'){document.dispatchEvent(new CustomEvent('votelab:open-vote-demo'));return;}
    if(practice)return;
    const dialog=document.createElement('dialog');dialog.className='ux-practice';dialog.setAttribute('aria-labelledby','practice-title');
    practice={role,step:0,name:'',description:'',photo:null,dialog,returnFocus:document.activeElement};document.body.append(dialog);
    dialog.addEventListener('close',()=>{if(practice?.photo)URL.revokeObjectURL(practice.photo);const focus=practice?.returnFocus;dialog.remove();practice=null;if(focus?.isConnected)focus.focus({preventScroll:true});});
    drawDemo();dialog.showModal();
  }
  function drawDemo(){
    const p=practice,d=p.dialog;
    const titles=[t('查看报名要求','Read entry requirements'),t('试填作品信息','Try entering your work'),t('核对演示作品','Review the practice entry'),t('演示提交审核','Practise submitting for review'),t('了解审核结果','Understand review outcomes')];
    d.innerHTML='<header><strong>'+t('演示 · 不保存真实记录','PRACTICE · No real records')+'</strong><button type="button" data-demo-close aria-label="'+t('关闭演示','Close practice')+'">×</button></header><small>'+ (p.step+1)+' / 5</small><h2 id="practice-title" tabindex="-1">'+titles[p.step]+'</h2><p class="helper">'+t('所有操作仅用于学习，不会创建活动、提交作品或投出真实选票。','Everything here is for learning. No event, entry submission or real ballot is created.')+'</p><div data-practice-content></div><footer><button class="text-button" type="button" data-demo-close>'+t('结束演示','End practice')+'</button>'+(p.step?'<button class="btn secondary" type="button" data-demo-back>'+t('上一步','Back')+'</button>':'')+'<button class="btn" type="button" data-demo-next>'+ (p.step===4?t('完成演示','Finish practice'):p.step===3?t('演示提交','Simulate submission'):t('下一步','Next'))+'</button></footer>';
    const content=d.querySelector('[data-practice-content]');
    if(p.step===0)content.innerHTML='<img class="practice-cover" src="/static/assets/example-projects.webp" alt=""><p>'+t('独立报名练习：试填一件作品。不会向创建者提交，不会进行真实审核。正式报名须在开放期间提交，由创建者审核。','Independent entry practice: try describing your work. No entry is sent to an organiser or actually reviewed. Real applications must be open and are reviewed by the creator.')+'</p>';
    if(p.step===1){
      content.innerHTML='<label class="field">'+t('作品名称（演示）','Entry title (practice)')+'<input data-practice-name maxlength="80"></label><label class="field">'+t('介绍（演示，可选）','Description (practice, optional)')+'<textarea data-practice-description maxlength="1000"></textarea></label><label class="field">'+t('可选图片 · 仅本机预览','Optional image · local preview only')+'<input type="file" data-practice-photo accept="image/jpeg,image/png,image/webp"></label><img class="practice-thumb" hidden alt="'+t('演示图片预览','Practice image preview')+'"><p data-practice-error role="status"></p>';
      content.querySelector('[data-practice-name]').value=p.name;content.querySelector('textarea').value=p.description;
      const preview=content.querySelector('img');if(p.photo){preview.src=p.photo;preview.hidden=false;}
      content.querySelector('[data-practice-name]').oninput=e=>p.name=e.target.value;content.querySelector('textarea').oninput=e=>p.description=e.target.value;
      content.querySelector('[type=file]').onchange=e=>{const f=e.target.files[0];if(!f)return;const error=content.querySelector('[data-practice-error]');if(!['image/jpeg','image/png','image/webp'].includes(f.type)||f.size>5*1024*1024){error.textContent=t('请选择5MB以内的JPEG、PNG或WebP图片。','Choose a JPEG, PNG or WebP image up to 5 MB.');return;}error.textContent='';if(p.photo)URL.revokeObjectURL(p.photo);p.photo=URL.createObjectURL(f);preview.src=p.photo;preview.hidden=false;};
    }
    if(p.step===2){const summary=document.createElement('p');summary.className='practice-summary';summary.textContent=(p.name.trim()||t('示例作品（尚未填写名称）','Example entry (no title entered)'))+(p.description?' — '+p.description:'');content.append(summary);content.insertAdjacentHTML('beforeend','<p>'+t('这里仅核对练习内容，不需要填写完整也可以继续了解。','This is a practice preview. You may continue learning without completing every field.')+'</p>');}
    if(p.step===3)content.innerHTML='<p>'+t('点击“演示提交”只改变练习窗口，不会真的报名。真实报名仍需要在实际活动中点击提交审核。','Simulate submission only changes this practice window. Real applications require Submit for review in an actual event.')+'</p>';
    if(p.step===4)content.innerHTML='<div class="notice info">'+t('模拟状态：待审核。这不是一份真实报名。','Simulated status: Pending review. No real entry was submitted.')+'</div><p>'+t('真实报名后可在“我的作品”查看状态。通过后按活动安排展示；被驳回时查看原因，报名仍开放且未截止时可修改重交。','After a real application, check My entries for the actual status. Read rejection feedback and resubmit only while applications remain open and before the deadline.')+'</p>';

    d.querySelectorAll('[data-demo-close]').forEach(b=>b.onclick=()=>d.close());
    d.querySelector('[data-demo-back]')?.addEventListener('click',()=>{p.step--;drawDemo();});
    d.querySelector('[data-demo-next]').onclick=()=>{if(p.step===4)d.close();else{p.step++;drawDemo();}};
    d.querySelector('h2').focus({preventScroll:true});
  }
  document.addEventListener('click',e=>{
    const trigger=e.target.closest('[data-guide-open],[data-practice-open]');if(!trigger)return;
    if(practice)return;origin=trigger;dismissHint();
    if(trigger.hasAttribute('data-practice-open'))return demo(trigger.dataset.practiceOpen);
    if(roles[trigger.dataset.guideRole]){guide={role:trigger.dataset.guideRole,step:0,template:trigger.dataset.guideTemplate||'custom'};render();}else choose();
  });
  document.addEventListener('votelab:learning-open',()=>{dismissHint();if(panel){if(guide)render();else choose();}});
  document.addEventListener('votelab:learning-close',event=>{if(panel&&event.detail.dialog.contains(panel))close();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&panel&&!practice&&!$('#ux-notice[open]')&&!$('.demo-image-view[open]')){if(learningHost())e.preventDefault();close();}});
  const hint=$('[data-guide-hint]'),seen='votelab-guide-seen-'+document.body.dataset.guideUser;
  function dismissHint(){if(!hint)return;hint.hidden=true;try{localStorage.setItem(seen,'1');}catch(_){}}
  if(hint){
    try{if(localStorage.getItem(seen))hint.hidden=true;}catch(_){}
    function placeHint(){const button=$('.guide-open');if(!button||hint.hidden)return;const r=button.getBoundingClientRect(),width=hint.getBoundingClientRect().width,left=Math.max(16,Math.min(innerWidth-width-16,r.right-width));hint.style.left=left+'px';hint.style.right='auto';hint.style.top=(r.bottom+15)+'px';hint.style.setProperty('--hint-arrow',Math.max(15,Math.min(width-25,r.left+r.width/2-left))+'px');}
    hint.querySelector('[data-dismiss-hint]').onclick=dismissHint;placeHint();window.addEventListener('resize',placeHint);
  }
  if(guide)render();
})();

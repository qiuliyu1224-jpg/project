/* One complete, temporary demo. No business requests, account or database writes. */
(() => {
  'use strict';
  const zh=document.documentElement.lang.startsWith('zh'),t=(a,b)=>zh?a:b;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const entries=[
    {asset:'entries',name:t('光与廊影','Light and arches'),description:t('树影与石拱之间，记录自然光带来的层次。','Natural light traces soft layers across stone arches and trees.')},
    {asset:'choice',name:t('纸上构想','An idea on paper'),description:t('从手绘草图和材质出发，探索空间的可能。','A study of space, expressed through sketches and natural materials.')},
    {asset:'projects',name:t('静谧空间','A quiet space'),description:t('木材、留白与光线，构成安静而开放的空间。','Wood, light and open space create a calm place to pause.')}
  ];
  let active=null;
  const image=entry=>'/static/assets/example-'+entry.asset+'.webp';
  const arrow='<span aria-hidden="true">→</span>';
  function makeDialog(className,title){
    const dialog=document.createElement('dialog');dialog.className=className;dialog.dataset.learningDialog='';
    dialog.setAttribute('aria-label',title);document.body.append(dialog);return dialog;
  }
  function restoreFocus(element){if(element?.isConnected)element.focus({preventScroll:true});}
  function openLearning(dialog){dialog.showModal();document.dispatchEvent(new CustomEvent('votelab:learning-open',{detail:{dialog}}));}
  function cleanup(dialog,returnFocus){
    document.dispatchEvent(new CustomEvent('votelab:learning-close',{detail:{dialog}}));
    dialog.remove();active=null;document.body.classList.remove('learning-open');restoreFocus(returnFocus);
  }
  function bindImageFallback(host){host.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{
    img.hidden=true;const note=img.parentElement.querySelector('[data-image-unavailable]');if(note)note.hidden=false;
    const zoom=img.closest('[data-demo-zoom]');if(zoom)zoom.disabled=true;
  }));}
  function zoom(index){
    if(!active||document.querySelector('.demo-image-view[open]'))return;
    const returnFocus=document.activeElement,entry=entries[index],dialog=makeDialog('demo-image-view',entry.name);
    delete dialog.dataset.learningDialog;
    dialog.innerHTML='<header><strong>'+entry.name+'</strong><button type="button" class="btn secondary" data-image-close>'+t('关闭图片','Close image')+' ×</button></header><div class="demo-large-photo"><img src="'+image(entry)+'" alt="'+entry.name+'"><p data-image-unavailable hidden>'+t('图片暂不可用，关闭后仍可阅读作品介绍。','Image unavailable. You can still read the entry description.')+'</p></div><p>'+entry.description+'</p>';
    dialog.querySelector('[data-image-close]').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{dialog.remove();restoreFocus(returnFocus);});
    bindImageFallback(dialog);dialog.showModal();
  }
  function openVote(){
    if(active)return;
    const dialog=makeDialog('vote-demo',t('作品评选演示','Entry evaluation demo'));
    active={kind:'vote',dialog,stage:'rating',scores:[null,null,null],submitted:null,busy:false,returnFocus:document.activeElement,timer:null};
    dialog.innerHTML='<header class="demo-header"><div><span class="demo-label">'+t('演示活动 · 非正式投票','DEMO EVENT · NOT A REAL VOTE')+'</span><h2>'+t('作品评选体验','Try entry evaluation')+'</h2></div><div class="demo-header-actions"><button type="button" class="btn secondary" data-guide-open data-guide-role="voter">'+t('投票指南','Voting guide')+'</button><button type="button" class="btn secondary" data-vote-demo-close>'+t('返回原页面','Back to previous page')+' ×</button></div></header><div class="demo-scope">'+t('可自由体验，记录仅用于当前示例。刷新、关闭或重新体验后，演示进度会清空。','Explore freely. Records belong only to this demo. Refreshing, closing or restarting clears demo progress.')+'</div><div class="demo-body" data-demo-body></div>';
    dialog.querySelector('[data-vote-demo-close]').onclick=()=>dialog.close();
    dialog.addEventListener('close',()=>{clearTimeout(active?.timer);cleanup(dialog,active?.returnFocus);});
    document.body.classList.add('learning-open');drawVote(false);openLearning(dialog);
  }
  function updateScore(index,value){
    if(active?.stage!=='rating')return;active.scores[index]=value;
    const card=active.dialog.querySelector('[data-demo-entry="'+index+'"]');
    card.querySelectorAll('[data-demo-score]').forEach(button=>{
      const n=Number(button.dataset.demoScore);button.setAttribute('aria-pressed',String(n===value));button.classList.toggle('is-selected',value!==null&&n>0&&n<=value);
    });
    const note=card.querySelector('[data-demo-rating]');note.textContent=value===null?t('未评分，不计入平均分','Not rated; excluded from the average'):value+' / 5';
    note.classList.remove('score-roll');void note.offsetWidth;note.classList.add('score-roll');
    active.dialog.querySelector('[data-demo-count]').textContent=countText();
    const error=active.dialog.querySelector('[data-demo-error]');error.hidden=true;
  }
  function countText(){const n=active.scores.filter(score=>score!==null).length;return t('已为 '+n+' / 3 件作品评分',n+' / 3 entries rated');}
  function burst(button){
    if(reduced)return;button.classList.remove('is-burst');void button.offsetWidth;button.classList.add('is-burst');
    for(let i=0;i<8;i++){const p=document.createElement('i');p.className='star-particle';p.setAttribute('aria-hidden','true');const angle=i*Math.PI/4;p.style.setProperty('--dx',Math.cos(angle)*29+'px');p.style.setProperty('--dy',Math.sin(angle)*27+'px');button.append(p);setTimeout(()=>p.remove(),650);}
    setTimeout(()=>button.classList.remove('is-burst'),650);
  }
  function rulePanel(){return '<aside class="demo-rules"><span class="eyebrow">'+t('先了解，再选择','READ BEFORE YOU CHOOSE')+'</span><h3>'+t('本场演示规则','Demo rules')+'</h3><ul><li>'+t('三件示例作品，至少评一件。','Three example entries. Rate at least one.')+'</li><li>'+t('0～5 分；0 分是有效评分。','Rate 0–5. Zero is a valid score.')+'</li><li>'+t('可以跳过作品，未评分不算 0 分。','You may skip an entry. Skipping is different from zero.')+'</li><li>'+t('先核对，再提交演示选票。','Review before submitting the demo ballot.')+'</li></ul><p>'+t('图片和作品仅为演示素材。演示不创建正式活动，也不计入“我的投票”、正式统计或导出。','Images and entries are demo materials. Nothing enters real events, My votes, real totals or exports.')+'</p><button class="text-button" type="button" data-guide-open data-guide-role="voter">'+t('打开五步投票指南','Open the five-step voting guide')+' '+arrow+'</button></aside>';}
  function drawVote(focus=true){
    if(active?.kind!=='vote')return;const a=active,host=a.dialog.querySelector('[data-demo-body]');
    const names=[t('评分','Rate'),t('核对','Review'),t('演示结果','Demo results')],step={rating:0,review:1,results:2}[a.stage];
    let html='<ol class="demo-steps" aria-label="'+t('体验进度','Demo progress')+'">'+names.map((name,i)=>'<li'+(i===step?' aria-current="step"':'')+'><span>'+(i+1)+'</span>'+name+'</li>').join('')+'</ol>';
    if(a.stage==='rating'){
      html+='<div class="demo-layout"><section><h3 tabindex="-1" data-demo-heading>'+t('看看作品，再给出你的评分','Explore the entries and choose your ratings')+'</h3><div class="demo-entries" data-demo-entries>';
      entries.forEach((entry,index)=>{const value=a.scores[index];html+='<article class="demo-work" data-demo-entry="'+index+'"><button type="button" class="demo-photo" data-demo-zoom="'+index+'" aria-label="'+t('放大查看：','Enlarge: ')+entry.name+'"><img src="'+image(entry)+'" alt="'+entry.name+'"><span data-image-unavailable hidden>'+t('图片暂不可用，仍可阅读下方介绍','Image unavailable. Read the description below.')+'</span><span class="demo-zoom-label">'+t('点击放大','Enlarge')+' ↗</span></button><div class="demo-work-copy"><span class="eyebrow">'+t('示例作品','EXAMPLE ENTRY')+' 0'+(index+1)+'</span><h4>'+entry.name+'</h4><p>'+entry.description+'</p><div class="demo-score-group" role="group" aria-label="'+entry.name+' · '+t('评分','rating')+'">'+[1,2,3,4,5].map(n=>'<button type="button" class="star-choice demo-star '+(value!==null&&n<=value?'is-selected':'')+'" data-demo-score="'+n+'" aria-label="'+n+' / 5" aria-pressed="'+(value===n)+'">★</button>').join('')+'<button type="button" class="demo-zero" data-demo-score="0" aria-label="'+t('0分','Zero points')+'" aria-pressed="'+(value===0)+'">0</button></div><div class="demo-rating-line"><span data-demo-rating aria-live="polite">'+(value===null?t('未评分，不计入平均分','Not rated; excluded from the average'):value+' / 5')+'</span><button class="text-button" type="button" data-demo-clear>'+t('清除','Clear')+'</button></div></div></article>';});
      html+='</div><p class="notice error" role="alert" data-demo-error hidden></p><footer class="demo-actions"><div><strong data-demo-count aria-live="polite">'+countText()+'</strong><small>'+t('当前只是选择，尚未提交。','Selections only. Nothing has been submitted.')+'</small></div><button type="button" class="btn demo-primary" data-demo-review>'+t('核对演示选票','Review demo ballot')+' '+arrow+'</button></footer></section>'+rulePanel()+'</div>';
    }else{
      const results=a.stage==='results',scores=results?a.submitted:a.scores;
      html+='<section class="demo-summary"><h3 tabindex="-1" data-demo-heading>'+t(results?'本次演示结果':'请核对你的选择',results?'Your demo results':'Review your selections')+'</h3><p>'+t(results?'演示投票成功。以下仅为你本次的评分，没有预置票数，也没有提交正式选票。':'这里只核对演示内容。你可以返回修改，确认后再提交演示选票。',results?'Demo vote complete. These are only your ratings, with no preset votes and no real ballot submitted.':'Review the demo selections. You can go back to edit before submitting.')+'</p><div class="demo-result-list">';
      entries.forEach((entry,index)=>{const value=scores[index];html+='<article class="demo-result" data-demo-result="'+index+'"><div class="demo-result-image"><img src="'+image(entry)+'" alt="'+entry.name+'"><span data-image-unavailable hidden>'+t('图片不可用','Image unavailable')+'</span></div><div><h4>'+entry.name+'</h4><p>'+(value===null?t('未评分 · 不计入平均分','Not rated · excluded from the average'):results?t('1 条演示评分 · 平均分 '+value.toFixed(2)+' / 5','1 demo rating · average '+value.toFixed(2)+' / 5'):t('本次选择：'+value+' / 5','Your selection: '+value+' / 5'))+'</p>'+(results&&value!==null?'<div class="demo-bar" aria-hidden="true"><span style="width:'+value*20+'%"></span></div>':'')+'</div><strong>'+(value===null?'—':value.toFixed(2)+' / 5')+'</strong></article>';});
      html+='</div><p class="helper">'+t('演示记录仅保留在当前窗口内，不进入正式活动、个人投票记录或导出文件。','Demo records stay in this window only, outside real events, personal ballot history and exports.')+'</p><footer class="demo-actions">'+(results?'<button type="button" class="btn secondary" data-demo-restart>'+t('重新体验','Try again')+'</button><button type="button" class="btn demo-primary" data-demo-return>'+t('返回活动广场','Return to Explore')+' '+arrow+'</button>':'<button type="button" class="btn secondary" data-demo-edit>'+t('返回修改','Back to edit')+'</button><div class="demo-submit-area"><small>'+t('仅保存到当前示例，不计入正式活动。','Only this demo is updated. Real events are unaffected.')+'</small><button type="button" class="btn demo-primary" data-demo-submit>'+t('提交演示选票','Submit demo ballot')+'</button></div>')+'</footer></section>';
    }
    host.innerHTML=html;bindImageFallback(host);
    host.querySelectorAll('[data-demo-zoom]').forEach(button=>button.onclick=()=>zoom(Number(button.dataset.demoZoom)));
    host.querySelectorAll('[data-demo-entry]').forEach(card=>{
      const index=Number(card.dataset.demoEntry);card.querySelectorAll('[data-demo-score]').forEach(button=>button.onclick=()=>{updateScore(index,Number(button.dataset.demoScore));if(button.dataset.demoScore!=='0')burst(button);});
      card.querySelector('[data-demo-clear]').onclick=()=>updateScore(index,null);
    });
    host.querySelector('[data-demo-review]')?.addEventListener('click',()=>{
      if(!a.scores.some(score=>score!==null)){const error=host.querySelector('[data-demo-error]');error.textContent=t('请至少为一件作品评分。0 分也可以；未评分的作品可以跳过。','Rate at least one entry. Zero is valid; other entries may be skipped.');error.hidden=false;error.scrollIntoView({block:'nearest',behavior:'instant'});return;}
      a.stage='review';drawVote();
    });
    host.querySelector('[data-demo-edit]')?.addEventListener('click',()=>{if(a.busy)return;a.stage='rating';drawVote();});
    host.querySelector('[data-demo-submit]')?.addEventListener('click',event=>{
      if(a.busy||a.submitted)return;a.busy=true;const button=event.currentTarget;button.disabled=true;button.classList.add('demo-submitting');button.setAttribute('aria-busy','true');button.textContent=t('正在完成演示…','Completing demo…');host.querySelector('[data-demo-edit]').disabled=true;
      // This timer is presentation only. No HTTP request or real save is made.
      a.timer=setTimeout(()=>{if(active!==a||!a.dialog.open)return;a.submitted=a.scores.slice();a.busy=false;a.stage='results';drawVote();},reduced?0:400);
    });
    host.querySelector('[data-demo-restart]')?.addEventListener('click',()=>{a.scores=[null,null,null];a.submitted=null;a.stage='rating';a.busy=false;drawVote();});
    host.querySelector('[data-demo-return]')?.addEventListener('click',()=>{a.dialog.close();if(location.pathname!=='/')location.assign('/');});
    if(focus){a.dialog.scrollTop=0;host.querySelector('[data-demo-heading]')?.focus({preventScroll:true});}
  }
  function openInfo(kind){
    if(active||!['choice','projects'].includes(kind))return;
    const choice=kind==='choice',title=choice?t('方案投票','Proposal voting'):t('项目展示','Project showcase');
    const dialog=makeDialog('example-details',title),returnFocus=document.activeElement;active={kind:'info',dialog};
    dialog.innerHTML='<header><span class="demo-label">'+t('展示示例 · 不能在此投票','DISPLAY EXAMPLE · NO VOTING HERE')+'</span><button type="button" class="btn secondary" data-info-close>'+t('关闭说明','Close details')+' ×</button></header><img class="example-detail-photo" src="/static/assets/example-'+kind+'.webp" alt="'+title+'"><h2>'+title+'</h2><p>'+t(choice?'适合比较多个备选方案，例如活动安排或设计方案。创建者可设为单选，或规定每人最多选择几项。':'适合介绍候选项目，让参与者了解目标与特点。这个示例介绍排序投票：按偏好排列项目；创建正式活动时也可以选择其他投票方式。',choice?'Compare alternatives such as event arrangements or design proposals. The creator can allow one choice or set a maximum number of choices.':'Introduce projects and their aims. This example explains ranking by preference. Real projects can also use other voting methods.')+'</p><p class="helper">'+t('这里仅介绍用途，不会创建活动或产生投票。想实际体验，可以返回首页的“作品评选”。','This explains the use case. No event or vote is created. For hands-on practice, try Entry evaluation on the home page.')+'</p><footer><button type="button" class="btn secondary" data-guide-open data-guide-role="creator" data-guide-template="'+(choice?'choice':'custom')+'">'+t('了解如何创建','Learn how to create')+' '+arrow+'</button></footer>';
    dialog.querySelector('[data-info-close]').onclick=()=>dialog.close();dialog.addEventListener('close',()=>cleanup(dialog,returnFocus));
    bindImageFallback(dialog);document.body.classList.add('learning-open');openLearning(dialog);
  }
  document.addEventListener('votelab:open-vote-demo',openVote);
  document.addEventListener('click',event=>{
    const start=event.target.closest('[data-vote-demo-open]');if(start){event.preventDefault();openVote();return;}
    const info=event.target.closest('[data-example-info]');if(info){event.preventDefault();openInfo(info.dataset.exampleInfo);}
  });
})();

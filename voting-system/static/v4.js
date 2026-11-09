// Version four feedback, ballot validation and live lifecycle checks.
(() => {
  const zh = document.documentElement.lang.startsWith('zh');
  const text = (a,b) => zh ? a : b;
  document.querySelectorAll('[data-get-code]').forEach(button => {
    button.addEventListener('click', async event => {
      event.preventDefault();
      const form = button.form;
      const phone = form.elements.phone;
      if (!phone.reportValidity()) return;
      const status = form.querySelector('[data-code-status]');
      const label = button.textContent;
      const body = new URLSearchParams();
      ['csrf', 'country', 'phone', 'purpose'].forEach(name => body.set(name, form.elements[name].value));
      button.disabled = true;
      button.textContent = text('正在获取…', 'Requesting…');
      status.hidden = false;
      status.classList.remove('error');
      status.textContent = text('正在获取验证码…', 'Requesting a verification code…');
      let received = false;
      try {
        const response = await fetch('/auth/code', {
          method: 'POST', credentials: 'same-origin',
          headers: {'Accept': 'application/json'}, body
        });
        const result = await response.json();
        if (!response.ok) {
          status.classList.add('error');
          status.textContent = result.error;
          return;
        }
        status.textContent = result.message + ' ';
        const code = document.createElement('strong');
        code.className = 'otp-code';
        code.textContent = result.code;
        status.append(code);
        received = true;
      } catch (_) {
        status.classList.add('error');
        status.textContent = text('暂时无法确认验证码请求，请稍后重试。已填写内容已保留。', 'The code request could not be confirmed. Try again shortly. Your entries have been kept.');
      } finally {
        button.disabled = false;
        button.textContent = label;
        if (received) {
          let remaining = 60;
          button.disabled = true;
          button.textContent = remaining + text('秒后重试', 's to retry');
          const timer = setInterval(() => {
            remaining -= 1;
            button.textContent = remaining + text('秒后重试', 's to retry');
            if (remaining === 0) {
              clearInterval(timer);
              button.disabled = false;
              button.textContent = label;
            }
          }, 1000);
        }
      }
    });
  });
  document.querySelectorAll('[data-show-password]').forEach(box => box.addEventListener('change', () => {
    box.closest('form').querySelectorAll('input[name="password"],input[name="password_confirm"]').forEach(input => input.type = box.checked ? 'text' : 'password');
  }));
  document.querySelectorAll('[data-clear-score]').forEach(button => button.addEventListener('click', () => {
    const stars=button.closest('.stars'); stars.querySelectorAll('input').forEach(input=>input.checked=false);
    stars.querySelectorAll('.is-selected').forEach(label=>label.classList.remove('is-selected'));
    stars.parentElement.querySelector('.selected-note').textContent=text('未评分，不计入平均分。','Not rated; excluded from the average.');
  }));
  document.querySelectorAll('img').forEach(img => img.addEventListener('error', () => {
    const fallback=img.parentElement.querySelector('.image-fallback');
    if(fallback) { img.hidden=true; fallback.hidden=false; }
    else { img.alt=text('图片暂不可用','Image temporarily unavailable'); }
  }));
  const eventForm=document.querySelector('[data-event-form]');
  if(eventForm) {
    const method=eventForm.querySelector('[name="method"]');
    const refresh=()=>{
      const single = method.value === 'SINGLE';
      const group = eventForm.querySelector('[data-choice-limit]');
      group.hidden = !single;
      group.querySelector('input').disabled = !single;
      group.querySelector('input').required = single;
      eventForm.querySelector('[data-majority-note]').hidden = method.value !== 'MAJORITY';
    };
    method.addEventListener('change',refresh); refresh();
  }
  const ballot=document.querySelector('[data-ballot]');
  if(ballot) {
    const counter=ballot.querySelector('[data-selection-count]');
    const count=()=>{if(counter) {const n=ballot.querySelectorAll('[name="candidate"]:checked').length; counter.textContent=ballot.dataset.method==='SINGLE' ? text('已选 ','Selected ')+n+' / '+ballot.dataset.limit : text('先核对，再提交。','Review before submitting.');}};
    ballot.addEventListener('change', count); count();
    ballot.addEventListener('submit',event=>{
      const method=ballot.dataset.method; let message='';
      if(method==='SINGLE'||method==='MAJORITY') {
        const n=ballot.querySelectorAll('[name="candidate"]:checked').length;
        const limit=method==='SINGLE'?Number(ballot.dataset.limit):1;
        if(n<1||n>limit)message=text('请选择1～','Choose 1–')+limit+text('个不同作品。',' different entries.');
      } else if(method==='SCORE') {
        if(!ballot.querySelector('[name^="score_"]:checked'))message=text('请至少为一个作品评分。','Rate at least one entry.');
      } else {
        const ranks=[...ballot.querySelectorAll('[name^="rank_"]')].filter(x=>x.value).map(x=>Number(x.value)).sort((a,b)=>a-b);
        if(!ranks.length||ranks.some((x,i)=>x!==i+1))message=text('请从1开始排序，不重复、不跳号。','Rank from 1 without duplicates or gaps.');
      }
      if(message){event.preventDefault();alert(message);}
    });
  }
  const status=document.querySelector('[data-event-status]');
  if(status) {
    let busy=false;
    const check=async()=>{
      if(busy||document.hidden)return; busy=true;
      try {
        const response=await fetch(status.dataset.eventStatus,{cache:'no-store'});
        if(!response.ok)return;
        const current=await response.json();
        if(current.status!==status.dataset.state||String(current.paused)!==status.dataset.paused||String(current.round)!==status.dataset.round) {
          ballot?.querySelectorAll('button,input,select').forEach(control=>control.disabled=true);
          location.reload();
        }
      } catch (_) { /* Keep current input during a transient network outage. */ }
      finally {busy=false;}
    };
    setInterval(check,10000); document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});
    if(Number(status.dataset.end)>0)setTimeout(check,Math.max(250,Math.min(2147483647,Number(status.dataset.end)*1000-Date.now()+300)));
  }
  document.querySelectorAll('form').forEach(form=>{
    form.addEventListener('invalid',event=>{
      event.target.setAttribute('aria-invalid','true');
    },true);
    form.addEventListener('input',event=>event.target.removeAttribute('aria-invalid'));
  });
})();

/* Render the already displayed chart locally; no data goes to another service. */
document.addEventListener('click', async event => {
  const button = event.target.closest('[data-export-png]');
  if (!button) return;
  const svg = document.querySelector('.result-chart svg');
  const status = document.querySelector('[data-export-status]');
  const zh = document.documentElement.lang.startsWith('zh');
  button.disabled = true;
  try {
    const copy = svg.cloneNode(true);
    // Remove translation controls but retain the original label as a fallback.
    copy.querySelectorAll('[data-translation-source]').forEach(node => {
      if (!node.dataset.englishTranslation) node.textContent = node.dataset.translationSource;
    });
    const box = svg.viewBox.baseVal;
    copy.setAttribute('width', box.width); copy.setAttribute('height', box.height);
    copy.removeAttribute('style');
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copy)], {type:'image/svg+xml;charset=utf-8'}));
    try {
      const img = new Image();
      await new Promise((resolve,reject) => {img.onload=resolve; img.onerror=reject; img.src=url;});
      const canvas = document.createElement('canvas');
      canvas.width=box.width*2; canvas.height=box.height*2;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle='#fff'; ctx.fillRect(0,0,canvas.width,canvas.height);
      ctx.drawImage(img,0,0,canvas.width,canvas.height);
      const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
      if (!blob) throw new Error('PNG unavailable');
      const png=URL.createObjectURL(blob), link=document.createElement('a');
      link.href=png; link.download=button.dataset.exportPng; link.click();
      setTimeout(()=>URL.revokeObjectURL(png),1000);
      status.textContent=zh?'已生成 PNG。':'PNG created.';
    } finally { URL.revokeObjectURL(url); }
  } catch (_) {status.textContent=zh?'无法生成 PNG，请下载 SVG。':'PNG could not be created. Download SVG instead.';}
  finally {button.disabled=false;}
});

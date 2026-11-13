// Online display translations. Stored originals and form fields remain unchanged.
(() => {
  if (!document.documentElement.lang.startsWith('en')) return;
  const nodes = [...document.querySelectorAll('[data-translation-token]')];
  if (!nodes.length) return;
  const csrf = document.querySelector('input[name="csrf"]')?.value;
  const notice = document.createElement('p');
  notice.className = 'helper translation-notice';
  notice.textContent = 'Activity text is automatically translated by MyMemory, an external online service. Translations may be inaccurate. Original submission fields are kept unchanged.';
  (document.querySelector('main') || document.body).prepend(notice);
  const groups = new Map();
  nodes.forEach(node => {
    const token = node.dataset.translationToken;
    if (!groups.has(token)) groups.set(token, []);
    groups.get(token).push(node);
  });
  const controls = new WeakMap();
  function originalControl(node) {
    // SVG text cannot contain HTML controls. Its associated HTML labels carry full names.
    if (node.namespaceURI === 'http://www.w3.org/2000/svg') return;
    if (controls.has(node)) return controls.get(node);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'text-button translation-original';
    button.textContent = 'View original';
    button.addEventListener('click', event => {
      event.preventDefault(); event.stopPropagation();
      const original = node.dataset.translationSource;
      const shown = button.dataset.originalShown === '1';
      node.textContent = shown ? (node.dataset.englishTranslation || 'Translation unavailable') : original;
      button.dataset.originalShown = shown ? '0' : '1';
      button.textContent = shown ? 'View original' : 'Show English';
    });
    node.after(button);
    controls.set(node, button);
    return button;
  }
  async function render(token, targets) {
    let translated = null;
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 16000);
      try {
        const response = await fetch('/translate', {
          method: 'POST', credentials: 'same-origin',
          headers: {'Accept': 'application/json'},
          body: new URLSearchParams({csrf: csrf || '', token}), signal: controller.signal
        });
        const result = await response.json();
        if (response.ok && result.ok && typeof result.text === 'string') translated = result.text;
      } finally { clearTimeout(timer); }
    } catch (_) { /* Keep failures local; voting must remain usable. */ }
    targets.forEach(node => {
      node.textContent = translated || 'Translation unavailable';
      node.dataset.englishTranslation = translated || '';
      originalControl(node);
      if (!translated && node.namespaceURI !== 'http://www.w3.org/2000/svg') {
        const retry = document.createElement('button');
        retry.type = 'button'; retry.className = 'text-button'; retry.textContent = 'Retry translation';
        retry.addEventListener('click', async event => {
          event.preventDefault(); event.stopPropagation(); retry.disabled = true;
          node.textContent = 'Translating...';
          await render(token, [node]); retry.remove();
        }, {once: true});
        node.after(retry);
      }
    });
  }
  const queue = [...groups.entries()];
  async function worker() {
    while (queue.length) { const [token, targets] = queue.shift(); await render(token, targets); }
  }
  Promise.all([worker(), worker()]);
})();

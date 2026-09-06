/* Browser reader. Markdown stays canonical; rendering never executes source code. */
(function () {
  'use strict';
  const config = window.DOC_SITE;
  const root = new URL('../', location.href);
  const reader = new URL('docs/read.html', root);
  const article = document.querySelector('#document');
  const status = document.querySelector('#status');
  const textExtensions = /\.(md|zig|zon|py|json|sh|txt|yaml|yml|js|css)$/i;
  const documents = new Set(config.documents || []);
  const assets = new Set(config.assets || []);

  // Keywords follow the exact Zig 0.16.0 lib/std/zig/tokenizer.zig release source.
  hljs.registerLanguage('zig', h => ({
    name: 'Zig', keywords: {
      keyword: 'addrspace align allowzero and anyframe anytype asm break callconv catch comptime const continue defer else enum errdefer error export extern fn for if inline noalias noinline nosuspend opaque or orelse packed pub resume return linksection struct suspend switch test threadlocal try union unreachable var volatile while',
      literal: 'true false null undefined', type: 'bool void noreturn type anyerror anyopaque usize isize comptime_int comptime_float f16 f32 f64 f80 f128'
    }, contains: [h.C_LINE_COMMENT_MODE, h.QUOTE_STRING_MODE, h.APOS_STRING_MODE,
      {scope: 'string', begin: /\\\\/, end: /$/},
      {scope: 'built_in', begin: /@[A-Za-z_][A-Za-z_0-9]*/},
      {scope: 'type', begin: /\b[ui]\d+\b/}, h.C_NUMBER_MODE]
  }));

  function pathOf(url) {
    if (url.origin !== root.origin || !url.pathname.startsWith(root.pathname)) return null;
    const path = decodeURIComponent(url.pathname.slice(root.pathname.length));
    if (!/^[A-Za-z0-9_./-]+$/.test(path) || path.split('/').some(x => x === '..' || x === '.')) return null;
    return path;
  }
  function repositorySource(link, path, fragment) {
    const repository = (config.directories || []).includes(path) ? config.repository.replace('/blob/', '/tree/') : config.repository;
    link.href = repository + path.split('/').map(encodeURIComponent).join('/') + fragment;
    link.classList.add('repository-link');
    link.title = 'View source on GitHub';
  }
  function resolveLinks(source) {
    article.querySelectorAll('a[href]').forEach(link => {
      const href = link.getAttribute('href');
      if (href.startsWith('#')) return;
      const target = new URL(href, source);
      const path = pathOf(target);
      if (path === null) { link.href = target.href; return; }
      if (config.public && !documents.has(path) && !assets.has(path)) {
        repositorySource(link, path, target.hash);
      } else if (textExtensions.test(path)) {
        const destination = new URL(reader);
        destination.searchParams.set('file', path);
        destination.hash = target.hash;
        link.href = destination.href;
      } else link.href = target.href;
    });
    article.querySelectorAll('img').forEach(img => {
      const target = new URL(img.getAttribute('src'), source);
      const path = pathOf(target);
      if (path === null || (config.public && !assets.has(path))) {
        img.replaceWith(document.createTextNode(img.alt || 'Image unavailable.'));
        return;
      }
      img.src = target.href;
      if (path.endsWith('.svg')) {
        const wrap = document.createElement('div'); wrap.className = 'image-scroll'; wrap.tabIndex = 0;
        wrap.setAttribute('aria-label', img.alt || 'Scrollable diagram'); img.replaceWith(wrap); wrap.append(img);
      }
    });
  }
  function addContents() {
    const counts = new Map();
    const toc = document.querySelector('#contents');
    article.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(heading => {
      const slug = heading.textContent.trim().toLowerCase().replace(/[^\p{L}\p{N}_ -]/gu, '').replace(/ /g, '-');
      const occurrence = counts.get(slug) || 0; counts.set(slug, occurrence + 1);
      heading.id = slug + (occurrence ? '-' + occurrence : '');
      if (!['H2', 'H3'].includes(heading.tagName)) return;
      const link = document.createElement('a'); link.href = '#' + heading.id; link.textContent = heading.textContent;
      if (heading.tagName === 'H3') link.className = 'sub';
      toc.append(link);
    });
  }
  async function copyCode(button, code) {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(code.textContent);
      else {
        const input = document.createElement('textarea'); input.value = code.textContent;
        input.style.position = 'fixed'; input.style.opacity = '0'; document.body.append(input); input.select();
        const copied = document.execCommand('copy'); input.remove(); if (!copied) throw new Error('Copy unavailable');
      }
      button.textContent = 'Copied';
    } catch (_) { button.textContent = 'Select text to copy'; }
  }
  function decorate() {
    article.querySelectorAll('pre code').forEach(code => {
      const label = [...code.classList].find(x => x.startsWith('language-'));
      if (label && hljs.getLanguage(label.slice(9))) hljs.highlightElement(code);
      const button = document.createElement('button'); button.className = 'copy'; button.type = 'button'; button.textContent = 'Copy';
      button.addEventListener('click', () => copyCode(button, code)); code.parentElement.prepend(button);
    });
    article.querySelectorAll('table').forEach(table => {
      const wrap = document.createElement('div'); wrap.className = 'table-scroll'; wrap.tabIndex = 0;
      wrap.setAttribute('aria-label', 'Scrollable table'); table.replaceWith(wrap); wrap.append(table);
    });
  }
  async function load() {
    const file = new URLSearchParams(location.search).get('file') || 'docs/ARCHITECTURE.md';
    // Validate the decoded query before URL normalization can erase dot segments.
    if (file.startsWith('/') || !/^[A-Za-z0-9_./-]+$/.test(file) || file.split('/').some(part => part === '.' || part === '..')) {
      throw new Error('Choose a document from the navigation.');
    }
    const source = new URL(file, root);
    const path = pathOf(source);
    if (path === null || !textExtensions.test(path)) throw new Error('Choose a document from the navigation.');
    if (config.public && !documents.has(path)) throw new Error('Choose a published guide from the navigation. Source files are available on GitHub.');
    source.search = '?raw=1';
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 10000);
    let body;
    try {
      const response = await fetch(source, {signal: controller.signal, credentials: 'same-origin'});
      if (!response.ok) throw new Error('The document could not be loaded (HTTP ' + response.status + ').');
      if (Number(response.headers.get('Content-Length')) > 1024 * 1024) throw new Error('This file exceeds the reader’s size limit.');
      body = await response.text();
      if (body.length > 1024 * 1024) throw new Error('This file exceeds the reader’s size limit.');
    } finally { clearTimeout(timer); }
    document.querySelector('#file-name').textContent = path;
    const raw = document.querySelector('#raw'); raw.href = source.href; raw.hidden = false;
    if (path.endsWith('.md')) {
      article.innerHTML = DOMPurify.sanitize(marked.parse(body), {USE_PROFILES: {html: true}});
      resolveLinks(source); addContents();
    } else {
      const heading = document.createElement('h1'); heading.textContent = path.split('/').pop();
      const pre = document.createElement('pre'); const code = document.createElement('code');
      const extension = path.split('.').pop();
      const language = {zon: 'zig', py: 'python', sh: 'bash', yml: 'yaml', js: 'javascript'}[extension] || extension;
      code.className = 'language-' + language; code.textContent = body; pre.append(code); article.append(heading, pre);
    }
    decorate();
    document.title = (article.querySelector('h1')?.textContent || path) + ' · bounded/http';
    if (config.public) document.querySelector('#repository-note').textContent = 'Source and evidence links open on GitHub.';
    status.hidden = true;
    if (location.hash) requestAnimationFrame(() => document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView());
    document.documentElement.dataset.readerReady = 'true';
  }
  document.querySelector('#print').addEventListener('click', () => window.print());
  load().catch(error => { status.textContent = error.message || 'The document could not be loaded.'; status.setAttribute('role', 'alert'); document.documentElement.dataset.readerReady = 'error'; });
})();

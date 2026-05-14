/* ET Films Mini App */

const tg = window.Telegram?.WebApp;
let initData = '';
let filter = 'all';
let page = 1;
let busy = false;
let debounce = null;

/* ── BOOT ────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  if (tg) {
    tg.ready();
    tg.expand();
    try { tg.setHeaderColor('#0a0a0f'); } catch {}
    try { tg.setBackgroundColor('#0a0a0f'); } catch {}
    initData = tg.initData || '';
  }

  /* Filter tab clicks */
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      filter = btn.dataset.f;
      loadFilms(true);
    });
  });

  /* Search input */
  const si = document.getElementById('s-input');
  si.addEventListener('input', () => {
    const v = si.value;
    document.getElementById('s-clear').classList.toggle('hidden', !v);
    clearTimeout(debounce);
    if (!v.trim()) {
      document.getElementById('s-results').innerHTML =
        '<div class="search-ph"><span>🎞</span><p>ፊልም ስም ያስገቡ</p></div>';
      return;
    }
    debounce = setTimeout(() => doSearch(v.trim()), 420);
  });

  await Promise.all([loadProfile(), loadFilms(true)]);
  showApp();
});

function showApp() {
  const sp = document.getElementById('splash');
  sp.classList.add('fade-out');
  setTimeout(() => {
    sp.style.display = 'none';
    document.getElementById('app').classList.remove('hidden');
  }, 480);
}

/* ── NAVIGATION ──────────────────────────────── */
function showPage(name, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nb').forEach(b => b.classList.remove('active'));
  const pg = document.getElementById('pg-' + name);
  if (pg) pg.classList.add('active');
  (btn || document.getElementById('nb-' + name))?.classList.add('active');
  if (name === 'search') setTimeout(() => document.getElementById('s-input').focus(), 120);
}

/* ── PROFILE ─────────────────────────────────── */
async function loadProfile() {
  try {
    const d = await api('/api/me');
    const name = [d.first_name, d.last_name].filter(Boolean).join(' ') || 'ስም የለም';
    document.getElementById('p-name').textContent = name;
    document.getElementById('p-uname').textContent = d.username ? '@' + d.username : '';
    document.getElementById('p-id').textContent = d.id || '—';

    const ini = ((d.first_name || '')[0] || '') + ((d.last_name || '')[0] || '');
    document.getElementById('av-init').textContent = ini || '👤';

    if (d.is_registered) {
      document.getElementById('p-bal').textContent = (d.balance || 0) + ' ብር';
      document.getElementById('p-phone').textContent = d.phone_number || '—';
      document.getElementById('p-refs').textContent = (d.referral_count || 0) + ' ሰዎች';
      document.getElementById('p-earn').textContent = (d.total_referral_earnings || 0) + ' ብር';
      document.getElementById('p-date').textContent = fmtDate(d.joined_date);

      const pill = document.getElementById('bal-pill');
      document.getElementById('bal-num').textContent = d.balance || 0;
      pill.classList.remove('hidden');
    } else {
      document.getElementById('no-reg').classList.remove('hidden');
    }
  } catch (e) {
    console.error('profile:', e);
  }
}

/* ── FILMS ───────────────────────────────────── */
async function loadFilms(reset) {
  if (busy) return;
  busy = true;
  if (reset) {
    page = 1;
    document.getElementById('grid').innerHTML =
      '<div class="spinner-wrap"><div class="spinner"></div><p>ፊልሞች እየጫናን ነው...</p></div>';
    document.getElementById('load-more').classList.add('hidden');
  }
  try {
    const qs = new URLSearchParams({ type: filter, page, initData });
    const d = await fetch('/api/films?' + qs, { headers: { 'X-Init-Data': initData } })
      .then(r => r.json());

    const grid = document.getElementById('grid');
    if (reset) grid.innerHTML = '';

    if (!d.films?.length) {
      if (reset) grid.innerHTML = '<div class="spinner-wrap"><p>ፊልሞች አልተገኙም</p></div>';
      document.getElementById('load-more').classList.add('hidden');
      return;
    }

    d.films.forEach(f => grid.appendChild(makeCard(f)));
    document.getElementById('load-more').classList.toggle('hidden', d.films.length < 20);
    page++;
  } catch (e) {
    console.error('films:', e);
    if (reset) document.getElementById('grid').innerHTML =
      '<div class="spinner-wrap"><p>ስህተት ተፈጠረ። እንደገና ይሞክሩ።</p></div>';
  } finally {
    busy = false;
  }
}

function loadMore() { loadFilms(false); }

/* ── SEARCH ──────────────────────────────────── */
function clearSearch() {
  document.getElementById('s-input').value = '';
  document.getElementById('s-clear').classList.add('hidden');
  document.getElementById('s-results').innerHTML =
    '<div class="search-ph"><span>🎞</span><p>ፊልም ስም ያስገቡ</p></div>';
}

async function doSearch(q) {
  const res = document.getElementById('s-results');
  res.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div><p>እየፈለግን ነው...</p></div>';
  try {
    const qs = new URLSearchParams({ q, type: 'all', initData });
    const d = await fetch('/api/films?' + qs, { headers: { 'X-Init-Data': initData } })
      .then(r => r.json());
    res.innerHTML = '';
    if (!d.films?.length) {
      res.innerHTML = '<div class="search-ph"><span>😕</span><p>"' + esc(q) + '" አልተገኘም</p></div>';
      return;
    }
    d.films.forEach(f => res.appendChild(makeCard(f)));
  } catch {
    res.innerHTML = '<div class="search-ph"><span>⚠️</span><p>ስህተት ተፈጠረ</p></div>';
  }
}

/* ── CARD BUILDER ────────────────────────────── */
function makeCard(f) {
  const div = document.createElement('div');
  div.className = 'card';

  const icon = f.type === 'series' ? '📺' : '🎬';
  const bc   = f.type === 'series' ? 'badge-e' : 'badge-s';
  const bl   = f.type === 'series' ? 'ተከታታይ' : 'ነጠላ ፊልም';
  const sz   = fmtSize(f.size);

  let title = (f.title || f.name || 'ፊልም').replace(/@\w+/g, '').replace(/\s+/g, ' ').trim();
  if (title.length > 90) title = title.slice(0, 90) + '…';

  div.innerHTML = `
    <div class="card-thumb">${icon}</div>
    <div class="card-body">
      <div class="card-title">${esc(title)}</div>
      <div class="card-meta">
        <span class="badge ${bc}">${bl}</span>
        ${sz ? `<span class="card-size">${sz}</span>` : ''}
      </div>
    </div>
    <div class="card-play">▶️</div>`;

  div.onclick = () => openPlayer(f.id, title);
  return div;
}

/* ── PLAYER ──────────────────────────────────── */
function openPlayer(filmId, title) {
  const url = `/stream/${filmId}?initData=${encodeURIComponent(initData)}`;
  document.getElementById('pl-title').textContent = title;
  document.getElementById('pl-fname').textContent = title;

  const vid = document.getElementById('vid');
  vid.src = url;
  document.getElementById('player').classList.remove('hidden');

  if (tg?.BackButton) {
    tg.BackButton.show();
    tg.BackButton.onClick(closePlayer);
  }
  vid.play().catch(() => {});
}

function closePlayer() {
  const vid = document.getElementById('vid');
  vid.pause();
  vid.removeAttribute('src');
  vid.load();
  document.getElementById('player').classList.add('hidden');
  if (tg?.BackButton) { tg.BackButton.hide(); tg.BackButton.offClick(closePlayer); }
}

/* ── HELPERS ─────────────────────────────────── */
async function api(url) {
  const r = await fetch(url, { headers: { 'X-Init-Data': initData } });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

function fmtSize(b) {
  if (!b) return '';
  const GB = b / 1073741824, MB = b / 1048576;
  if (GB >= 1) return GB.toFixed(1) + ' GB';
  if (MB >= 1) return Math.round(MB) + ' MB';
  return Math.round(b / 1024) + ' KB';
}

function fmtDate(s) {
  if (!s) return '—';
  try { return new Date(s).toLocaleDateString('en-GB'); } catch { return s.split('T')[0] || '—'; }
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

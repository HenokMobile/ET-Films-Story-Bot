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

  /* If not in Telegram, show a friendly notice */
  const inTelegram = !!(tg && tg.initData);
  if (!inTelegram) {
    showNoTelegramNotice();
    showApp();
    return;
  }

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

/* ── NOT-IN-TELEGRAM NOTICE ──────────────────── */
function showNoTelegramNotice() {
  const grid = document.getElementById('grid');
  if (grid) grid.innerHTML = `
    <div class="not-tg-notice">
      <div class="ntg-icon">📱</div>
      <h3>Telegram ውስጥ ይክፈቱ</h3>
      <p>ይህ Mini App ከ Telegram Bot ውስጥ ብቻ ይሰራል።</p>
      <p class="ntg-sub">Bot ላይ ሄደው <strong>🎬 ET Films</strong> button ይጫኑ።</p>
    </div>`;
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
let searchQuery = '';
let searchPage = 1;
let searchBusy = false;

function clearSearch() {
  document.getElementById('s-input').value = '';
  document.getElementById('s-clear').classList.add('hidden');
  document.getElementById('s-results').innerHTML =
    '<div class="search-ph"><span>🎞</span><p>ፊልም ስም ያስገቡ</p></div>';
  document.getElementById('s-load-more').classList.add('hidden');
  searchQuery = '';
  searchPage = 1;
}

async function doSearch(q) {
  searchQuery = q;
  searchPage = 1;
  const res = document.getElementById('s-results');
  res.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div><p>እየፈለግን ነው...</p></div>';
  document.getElementById('s-load-more').classList.add('hidden');
  await _fetchSearch(true);
}

async function searchLoadMore() {
  if (searchBusy || !searchQuery) return;
  await _fetchSearch(false);
}

async function _fetchSearch(reset) {
  if (searchBusy) return;
  searchBusy = true;
  const res = document.getElementById('s-results');
  const btn = document.getElementById('s-load-more');
  try {
    const qs = new URLSearchParams({ q: searchQuery, type: 'all', page: searchPage, initData });
    const d = await fetch('/api/films?' + qs, { headers: { 'X-Init-Data': initData } })
      .then(r => r.json());
    if (reset) res.innerHTML = '';
    if (!d.films?.length) {
      if (reset) res.innerHTML = '<div class="search-ph"><span>😕</span><p>"' + esc(searchQuery) + '" አልተገኘም</p></div>';
      btn.classList.add('hidden');
      return;
    }
    d.films.forEach(f => res.appendChild(makeCard(f)));
    btn.classList.toggle('hidden', d.films.length < 20);
    searchPage++;
  } catch {
    if (reset) res.innerHTML = '<div class="search-ph"><span>⚠️</span><p>ስህተት ተፈጠረ</p></div>';
  } finally {
    searchBusy = false;
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

  let title = (f.name || f.title || 'ፊልም').replace(/@\w+/g, '').replace(/\s+/g, ' ').trim();
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
let _currentStreamUrl = '';
let _hlsInstance = null;

function _playerReset() {
  const vid    = document.getElementById('vid');
  const load   = document.getElementById('vid-loading');
  const errDiv = document.getElementById('vid-error');
  const tapDiv = document.getElementById('vid-tap');
  /* destroy previous HLS instance */
  if (_hlsInstance) { _hlsInstance.destroy(); _hlsInstance = null; }
  /* reset video element */
  vid.pause();
  vid.removeAttribute('src');
  vid.load();
  vid.oncanplay = null; vid.onerror = null; vid.onstalled = null;
  vid.onplaying = null; vid.onwaiting = null;
  /* reset overlay states */
  vid.classList.add('hidden');
  load.classList.remove('hidden');
  errDiv.classList.add('hidden');
  tapDiv.classList.add('hidden');
  return { vid, load, errDiv, tapDiv };
}

function _attachVideoEvents(vid, load, errDiv, tapDiv) {
  vid.oncanplay = () => {
    load.classList.add('hidden');
    tapDiv.classList.remove('hidden');
    vid.classList.remove('hidden');
    vid.play().then(() => tapDiv.classList.add('hidden')).catch(() => {});
  };
  vid.onplaying = () => {
    load.classList.add('hidden');
    tapDiv.classList.add('hidden');
    vid.classList.remove('hidden');
  };
  vid.onstalled = vid.onwaiting = () => {
    if (!vid.error) load.classList.remove('hidden');
  };
  vid.onerror = () => {
    load.classList.add('hidden');
    tapDiv.classList.add('hidden');
    errDiv.classList.remove('hidden');
    vid.classList.add('hidden');
  };
}

async function openPlayer(filmId, title) {
  document.getElementById('pl-title').textContent = title;
  document.getElementById('pl-fname').textContent = title;
  document.getElementById('player').classList.remove('hidden');

  if (tg?.BackButton) { tg.BackButton.show(); tg.BackButton.onClick(closePlayer); }

  const { vid, load, errDiv, tapDiv } = _playerReset();

  /* Ask server: direct MP4 stream or HLS transcoding? */
  let info;
  try {
    const qs = new URLSearchParams({ initData });
    /* Show a "preparing" message while server starts HLS (can take ~5-10s) */
    const statusTxt = load.querySelector('.vid-status-txt');
    if (statusTxt) statusTxt.textContent = 'ፊልም እያዘጋጀን ነው…';
    const r = await fetch(
      `/api/stream/start/${filmId}?${qs}`,
      { headers: { 'X-Init-Data': initData } }
    );
    if (!r.ok) throw new Error('HTTP ' + r.status);
    info = await r.json();
    if (statusTxt) statusTxt.textContent = 'ፊልም እየጫናን ነው…';
  } catch (e) {
    load.classList.add('hidden');
    errDiv.classList.remove('hidden');
    return;
  }

  _currentStreamUrl = info.url;
  _attachVideoEvents(vid, load, errDiv, tapDiv);

  if (info.type === 'hls') {
    /* HLS path — use hls.js (required on Android Chrome) */
    if (typeof Hls !== 'undefined' && Hls.isSupported()) {
      const hls = new Hls({
        maxBufferLength: 30,
        maxMaxBufferLength: 60,
        lowLatencyMode: false,
      });
      _hlsInstance = hls;
      hls.loadSource(info.url);
      hls.attachMedia(vid);
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (data.fatal) {
          load.classList.add('hidden');
          errDiv.classList.remove('hidden');
          vid.classList.add('hidden');
        }
      });
    } else if (vid.canPlayType('application/vnd.apple.mpegurl')) {
      /* Native HLS (Safari iOS) */
      vid.src = info.url;
    } else {
      errDiv.classList.remove('hidden');
      load.classList.add('hidden');
    }
  } else {
    /* Direct MP4 — native <video> with byte-range seeking */
    vid.src = info.url;
  }
}

function closePlayer() {
  _playerReset();
  document.getElementById('player').classList.add('hidden');
  if (tg?.BackButton) { tg.BackButton.hide(); tg.BackButton.offClick(closePlayer); }
}

function downloadFilm() {
  if (_currentStreamUrl) window.open(_currentStreamUrl, '_blank');
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

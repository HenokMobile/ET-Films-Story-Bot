/* ET Films Mini App */

const tg = window.Telegram?.WebApp;
let initData = '';
let page = 1;
let busy = false;
let debounce = null;
let isSearchMode = false;
let searchQuery = '';
let searchPage = 1;
let searchBusy = false;

/* ── BOOT ────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  if (tg) {
    tg.ready();
    tg.expand();
    try { tg.setHeaderColor('#0a0a0f'); } catch {}
    try { tg.setBackgroundColor('#0a0a0f'); } catch {}
    initData = tg.initData || '';
  }

  /* Search input listener */
  const si = document.getElementById('s-input');
  si.addEventListener('input', () => {
    const v = si.value;
    document.getElementById('s-clear').classList.toggle('hidden', !v);
    clearTimeout(debounce);
    if (!v.trim()) {
      isSearchMode = false;
      searchQuery = '';
      document.getElementById('section-hdr').querySelector('.section-title').textContent = '🎬 ፊልሞች';
      document.getElementById('section-count').textContent = '';
      document.getElementById('load-more').classList.add('hidden');
      loadFilms(true);
      return;
    }
    debounce = setTimeout(() => doSearch(v.trim()), 400);
  });

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

/* ── PROFILE ─────────────────────────────────── */
async function loadProfile() {
  try {
    const d = await api('/api/me');
    const name = [d.first_name, d.last_name].filter(Boolean).join(' ') || 'ስም የለም';
    const firstName = d.first_name || name;

    /* Header greeting */
    document.getElementById('h-name').textContent = firstName;

    /* Drawer */
    document.getElementById('p-name').textContent = name;
    document.getElementById('p-uname').textContent = d.username ? '@' + d.username : '';
    document.getElementById('p-id').textContent = d.id || '—';

    /* Profile photo from Telegram WebApp */
    const tgUser = tg?.initDataUnsafe?.user;
    const photoUrl = tgUser?.photo_url || null;

    if (photoUrl) {
      /* Header icon */
      const hPhoto = document.getElementById('prof-photo');
      const hInit = document.getElementById('prof-init');
      hPhoto.src = photoUrl;
      hPhoto.classList.remove('hidden');
      hInit.classList.add('hidden');
      /* Drawer */
      const dPhoto = document.getElementById('d-photo');
      const dInit = document.getElementById('d-init');
      dPhoto.src = photoUrl;
      dPhoto.classList.remove('hidden');
      dInit.classList.add('hidden');
    } else {
      const ini = ((d.first_name || '')[0] || '') + ((d.last_name || '')[0] || '');
      if (ini) {
        document.getElementById('prof-init').textContent = ini.toUpperCase();
        document.getElementById('d-init').textContent = ini.toUpperCase();
      }
    }

    if (d.is_registered) {
      const bal = d.balance || 0;
      document.getElementById('p-bal').textContent = bal + ' ብር';
      document.getElementById('p-phone').textContent = d.phone_number || '—';
      document.getElementById('p-refs').textContent = (d.referral_count || 0) + ' ሰዎች';
      document.getElementById('p-earn').textContent = (d.total_referral_earnings || 0) + ' ብር';
      document.getElementById('p-date').textContent = fmtDate(d.joined_date);

      document.getElementById('bal-num').textContent = bal;
      document.getElementById('bal-pill').classList.remove('hidden');
    } else {
      document.getElementById('no-reg').classList.remove('hidden');
    }
  } catch (e) {
    console.error('profile:', e);
  }
}

/* ── PROFILE DRAWER ──────────────────────────── */
function openProfile() {
  document.getElementById('profile-overlay').classList.remove('hidden');
  document.getElementById('profile-drawer').classList.remove('hidden');
  if (tg?.BackButton) { tg.BackButton.show(); tg.BackButton.onClick(closeProfile); }
}

function closeProfile() {
  document.getElementById('profile-overlay').classList.add('hidden');
  document.getElementById('profile-drawer').classList.add('hidden');
  if (tg?.BackButton) { tg.BackButton.hide(); tg.BackButton.offClick(closeProfile); }
}

/* ── FILMS (home grid) ───────────────────────── */
async function loadFilms(reset) {
  if (busy) return;
  busy = true;
  isSearchMode = false;
  if (reset) {
    page = 1;
    document.getElementById('grid').innerHTML =
      '<div class="spinner-wrap full"><div class="spinner"></div><p>ፊልሞች እየጫናን ነው...</p></div>';
    document.getElementById('load-more').classList.add('hidden');
  }
  try {
    const qs = new URLSearchParams({ type: 'all', page, initData });
    const d = await fetch('/api/films?' + qs, { headers: { 'X-Init-Data': initData } })
      .then(r => r.json());

    const grid = document.getElementById('grid');
    if (reset) grid.innerHTML = '';

    if (!d.films?.length) {
      if (reset) grid.innerHTML = '<div class="spinner-wrap full"><p>ፊልሞች አልተገኙም</p></div>';
      document.getElementById('load-more').classList.add('hidden');
      return;
    }

    d.films.forEach(f => grid.appendChild(makeTile(f)));
    document.getElementById('load-more').classList.toggle('hidden', d.films.length < 21);
    page++;
  } catch (e) {
    console.error('films:', e);
    if (reset) document.getElementById('grid').innerHTML =
      '<div class="spinner-wrap full"><p>ስህተት ተፈጠረ። እንደገና ይሞክሩ።</p></div>';
  } finally {
    busy = false;
  }
}

function loadMore() {
  if (isSearchMode) searchLoadMore();
  else loadFilms(false);
}

/* ── SEARCH ──────────────────────────────────── */
function clearSearch() {
  document.getElementById('s-input').value = '';
  document.getElementById('s-clear').classList.add('hidden');
  isSearchMode = false;
  searchQuery = '';
  searchPage = 1;
  document.getElementById('section-hdr').querySelector('.section-title').textContent = '🎬 ፊልሞች';
  document.getElementById('section-count').textContent = '';
  loadFilms(true);
}

async function doSearch(q) {
  isSearchMode = true;
  searchQuery = q;
  searchPage = 1;
  document.getElementById('section-hdr').querySelector('.section-title').textContent = '🔍 ፍለጋ: ' + q;
  document.getElementById('section-count').textContent = '';
  const grid = document.getElementById('grid');
  grid.innerHTML = '<div class="spinner-wrap full"><div class="spinner"></div><p>እየፈለግን ነው...</p></div>';
  document.getElementById('load-more').classList.add('hidden');
  await _fetchSearch(true);
}

async function searchLoadMore() {
  if (searchBusy || !searchQuery) return;
  await _fetchSearch(false);
}

async function _fetchSearch(reset) {
  if (searchBusy) return;
  searchBusy = true;
  const grid = document.getElementById('grid');
  const btn = document.getElementById('load-more');
  try {
    const qs = new URLSearchParams({ q: searchQuery, type: 'all', page: searchPage, initData });
    const d = await fetch('/api/films?' + qs, { headers: { 'X-Init-Data': initData } })
      .then(r => r.json());
    if (reset) grid.innerHTML = '';
    if (!d.films?.length) {
      if (reset) grid.innerHTML = '<div class="search-ph"><span>😕</span><p>"' + esc(searchQuery) + '" አልተገኘም</p></div>';
      btn.classList.add('hidden');
      return;
    }
    d.films.forEach(f => grid.appendChild(makeTile(f)));
    const count = d.total || d.films.length;
    document.getElementById('section-count').textContent = count + ' ፊልሞች';
    btn.classList.toggle('hidden', d.films.length < 21);
    searchPage++;
  } catch {
    if (reset) grid.innerHTML = '<div class="search-ph"><span>⚠️</span><p>ስህተት ተፈጠረ</p></div>';
  } finally {
    searchBusy = false;
  }
}

/* ── TILE BUILDER (2-col grid) ───────────────── */
function makeTile(f) {
  const div = document.createElement('div');
  div.className = 'film-tile';

  const sz = fmtSize(f.size);
  let title = (f.name || f.title || 'ፊልም').replace(/@\w+/g, '').replace(/\s+/g, ' ').trim();
  if (title.length > 60) title = title.slice(0, 60) + '…';

  const holes = Array(5).fill('<div class="film-hole"></div>').join('');
  const posterHtml = f.poster_url
    ? `<img class="tile-poster" src="${esc(f.poster_url)}" alt="${esc(title)}" loading="lazy" onerror="this.style.display='none'">`
    : '';
  div.innerHTML = `
    <div class="tile-thumb">
      ${posterHtml}
      <div class="film-strip-top">${holes}</div>
      <div class="tile-play-center"><div class="tile-play-arrow"></div></div>
      <div class="film-strip-bot">${holes}</div>
    </div>
    <div class="tile-body">
      <div class="tile-title">${esc(title)}</div>
      ${sz ? `<div class="tile-size">${sz}</div>` : ''}
    </div>`;

  div.onclick = () => openDetail(f, title);
  return div;
}

/* ── FILM DETAIL DRAWER ──────────────────────── */
let _detailFilm = null;

function openDetail(f, title) {
  _detailFilm = f;

  // Poster
  const poster    = document.getElementById('detail-poster');
  const noPoster  = document.getElementById('detail-no-poster');
  if (f.poster_url) {
    poster.src = f.poster_url;
    poster.classList.remove('hidden');
    noPoster.classList.add('hidden');
    poster.onerror = () => { poster.classList.add('hidden'); noPoster.classList.remove('hidden'); };
  } else {
    poster.src = '';
    poster.classList.add('hidden');
    noPoster.classList.remove('hidden');
  }

  // Badge (series or movie)
  const badge = document.getElementById('detail-badge');
  badge.textContent = f.type === 'series' ? '📺 ድራማ' : '🎬 ፊልም';

  // Title
  document.getElementById('detail-title').textContent = title;

  // Meta: size + type
  const sz = fmtSize(f.size);
  const meta = document.getElementById('detail-meta');
  meta.innerHTML = [
    sz ? `<span>📦 ${sz}</span>` : '',
    f.type === 'series' ? '<span>📺 ተከታታይ ድራማ</span>' : '<span>🎥 ነጠላ ፊልም</span>',
  ].filter(Boolean).join('<span style="opacity:.3">·</span>');

  // Play button
  document.getElementById('detail-play-btn').onclick = () => {
    closeDetail();
    openPlayer(f.id, title);
  };

  // Show drawer
  document.getElementById('detail-overlay').classList.remove('hidden');
  document.getElementById('detail-drawer').classList.remove('hidden');

  if (tg?.BackButton) { tg.BackButton.show(); tg.BackButton.onClick(closeDetail); }
}

function closeDetail() {
  document.getElementById('detail-overlay').classList.add('hidden');
  document.getElementById('detail-drawer').classList.add('hidden');
  _detailFilm = null;
  if (tg?.BackButton) { tg.BackButton.hide(); tg.BackButton.offClick(closeDetail); }
}

/* ── PLAYER ──────────────────────────────────── */
let _currentStreamUrl = '';
let _hlsInstance = null;

function _playerReset() {
  const vid    = document.getElementById('vid');
  const load   = document.getElementById('vid-loading');
  const errDiv = document.getElementById('vid-error');
  const tapDiv = document.getElementById('vid-tap');
  if (_hlsInstance) { _hlsInstance.destroy(); _hlsInstance = null; }
  vid.pause();
  vid.removeAttribute('src');
  vid.load();
  vid.oncanplay = null; vid.onerror = null; vid.onstalled = null;
  vid.onplaying = null; vid.onwaiting = null;
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

  let info;
  try {
    const qs = new URLSearchParams({ initData });
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
    if (typeof Hls !== 'undefined' && Hls.isSupported()) {
      const hls = new Hls({ maxBufferLength: 30, maxMaxBufferLength: 60, lowLatencyMode: false });
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
      vid.src = info.url;
    } else {
      errDiv.classList.remove('hidden');
      load.classList.add('hidden');
    }
  } else {
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

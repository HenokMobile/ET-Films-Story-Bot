/* ET Films Mini App */

const tg = window.Telegram?.WebApp;
let initData = '';
let webToken = localStorage.getItem('et_web_token') || '';
let _loginPhone = '';
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

  if (!inTelegram && !webToken) {
    showLoginPage();
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

/* ── LOGIN PAGE ──────────────────────────────── */
function showLoginPage() {
  document.getElementById('login-page').classList.remove('hidden');
  document.getElementById('app').classList.add('hidden');
}

function hideLoginPage() {
  document.getElementById('login-page').classList.add('hidden');
}

function showPhoneStep() {
  document.getElementById('login-step-phone').classList.remove('hidden');
  document.getElementById('login-step-otp').classList.add('hidden');
  loginClearError('phone');
}

function loginClearError(type) {
  document.getElementById('login-' + type + '-error').classList.add('hidden');
}

function loginShowError(type, msg) {
  const el = document.getElementById('login-' + type + '-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function loginSetLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  btn.disabled = loading;
  if (btnId === 'login-phone-btn') btn.textContent = loading ? 'እየላክን...' : 'ቀጥል →';
  if (btnId === 'login-otp-btn')   btn.textContent = loading ? 'እያረጋገጥን...' : 'ፀድቅ ✓';
}

async function requestOtp() {
  const phone = document.getElementById('login-phone').value.trim();
  if (!phone) { loginShowError('phone', 'ስልክ ቁጥር ያስገቡ'); return; }

  loginSetLoading('login-phone-btn', true);
  loginClearError('phone');

  try {
    const r = await fetch('/api/auth/request-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone }),
    });
    const d = await r.json();
    if (!r.ok) { loginShowError('phone', d.error || 'ስህተት ተፈጠረ'); return; }

    _loginPhone = phone;
    document.getElementById('otp-desc').textContent = `${phone} — Telegram ላይ ኮድ ተልኳል`;
    document.getElementById('login-step-phone').classList.add('hidden');
    document.getElementById('login-step-otp').classList.remove('hidden');
    document.getElementById('login-otp').value = '';
    document.getElementById('login-otp').focus();
  } catch (e) {
    loginShowError('phone', 'ኔትወርክ ስህተት። እንደገና ይሞክሩ');
  } finally {
    loginSetLoading('login-phone-btn', false);
  }
}

async function verifyOtp() {
  const otp = document.getElementById('login-otp').value.trim();
  if (!otp) { loginShowError('otp', 'ኮዱን ያስገቡ'); return; }

  loginSetLoading('login-otp-btn', true);
  loginClearError('otp');

  try {
    const r = await fetch('/api/auth/verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: _loginPhone, otp }),
    });
    const d = await r.json();
    if (!r.ok) { loginShowError('otp', d.error || 'ስህተት ተፈጠረ'); return; }

    webToken = d.token;
    localStorage.setItem('et_web_token', webToken);
    hideLoginPage();
    await Promise.all([loadProfile(), loadFilms(true)]);
    showApp();
  } catch (e) {
    loginShowError('otp', 'ኔትወርክ ስህተት። እንደገና ይሞክሩ');
  } finally {
    loginSetLoading('login-otp-btn', false);
  }
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
    const qs = new URLSearchParams({ type: 'all', page });
    const d = await fetch('/api/films?' + qs, { headers: _authHeaders() })
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
    const qs = new URLSearchParams({ q: searchQuery, type: 'all', page: searchPage });
    const d = await fetch('/api/films?' + qs, { headers: _authHeaders() })
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

/* ── FILM DETAIL FULL SCREEN ─────────────────── */
let _detailFilm  = null;
let _carouselIdx = 0;
let _carouselLen = 0;

async function openDetail(f, title) {
  _detailFilm = f;

  const page = document.getElementById('detail-page');
  const loading = document.getElementById('detail-loading');
  const scroll  = document.getElementById('detail-scroll');

  // Show full screen with spinner
  page.classList.remove('hidden');
  loading.classList.remove('hidden');
  scroll.classList.add('hidden');

  if (tg?.BackButton) { tg.BackButton.show(); tg.BackButton.onClick(closeDetail); }

  // Play button wired immediately
  document.getElementById('detail-play-btn').onclick = () => {
    closeDetail();
    openPlayer(f.id, title);
  };

  // Fetch TMDB detail
  let tmdb = {};
  try {
    const qs = new URLSearchParams({ title: f.name || f.title || '', type: f.type || 'movie' });
    tmdb = await fetch('/api/tmdb_detail?' + qs).then(r => r.json());
  } catch (e) { console.warn('tmdb_detail:', e); }

  // ── Carousel ──────────────────────────────────
  const track = document.getElementById('carousel-track');
  const dotsEl = document.getElementById('carousel-dots');
  track.innerHTML = '';
  dotsEl.innerHTML = '';
  _carouselIdx = 0;

  // backdrops (w780 URLs) are landscape; original-size images from posters are portrait
  const rawImages = (tmdb.images && tmdb.images.length) ? tmdb.images
                  : f.poster_url ? [f.poster_url] : [];
  _carouselLen = rawImages.length;

  rawImages.forEach((src, i) => {
    // heuristic: w780 = backdrop (landscape), /original/ without w780 = poster (portrait)
    const isPortrait = src.includes('/original/') && !src.includes('/w780');
    const slide = document.createElement('div');
    slide.className = 'carousel-slide' + (isPortrait ? ' portrait' : '');
    slide.innerHTML = `<img src="${esc(src)}" loading="${i === 0 ? 'eager' : 'lazy'}" alt=""><div class="carousel-slide-fade"></div>`;
    track.appendChild(slide);

    const dot = document.createElement('div');
    dot.className = 'dot' + (i === 0 ? ' active' : '');
    dotsEl.appendChild(dot);
  });

  // Update dots on scroll
  track.onscroll = () => {
    const idx = Math.round(track.scrollLeft / track.clientWidth);
    if (idx !== _carouselIdx) {
      _carouselIdx = idx;
      dotsEl.querySelectorAll('.dot').forEach((d, i) => d.classList.toggle('active', i === idx));
    }
  };

  // ── Info ──────────────────────────────────────
  const displayTitle = tmdb.tmdb_title || title;
  document.getElementById('detail-badge').textContent = f.type === 'series' ? '📺 ድራማ' : '🎬 ፊልም';
  document.getElementById('detail-title').textContent = displayTitle;

  // Stats row
  const stats = document.getElementById('detail-stats');
  const statParts = [];
  if (tmdb.rating) statParts.push(`<div class="stat-pill gold">⭐ ${tmdb.rating}</div>`);
  if (tmdb.year)   statParts.push(`<div class="stat-pill">📅 ${tmdb.year}</div>`);
  if (tmdb.runtime) {
    const h = Math.floor(tmdb.runtime / 60), m = tmdb.runtime % 60;
    const rt = h ? `${h}ሰ ${m}ደ` : `${m}ደ`;
    statParts.push(`<div class="stat-pill">⏱ ${rt}</div>`);
  }
  // Film type pill (series / movie) — prefer TMDB's confirmed kind
  const kindLabel = f.type === 'series' ? '📺 ተከታታይ' : '🎬 ነጠላ ፊልም';
  statParts.push(`<div class="stat-pill">${kindLabel}</div>`);
  // Country of origin
  if (tmdb.country) statParts.push(`<div class="stat-pill">🌍 ${esc(tmdb.country)}</div>`);
  // File size
  const sz = fmtSize(f.size);
  if (sz) statParts.push(`<div class="stat-pill">📦 ${sz}</div>`);
  stats.innerHTML = statParts.join('');

  // Genres
  const genresEl = document.getElementById('detail-genres');
  genresEl.innerHTML = (tmdb.genres || []).map(g => `<span class="genre-tag">${esc(g)}</span>`).join('');

  // Overview
  const ovWrap = document.getElementById('detail-overview-wrap');
  const ovEl   = document.getElementById('detail-overview');
  if (tmdb.overview) {
    ovEl.textContent = tmdb.overview;
    ovWrap.classList.remove('hidden');
  } else { ovWrap.classList.add('hidden'); }

  // Director
  const dirWrap = document.getElementById('detail-director-wrap');
  const dirEl   = document.getElementById('detail-director');
  if (tmdb.directors && tmdb.directors.length) {
    dirEl.textContent = tmdb.directors.join(', ');
    dirWrap.classList.remove('hidden');
  } else { dirWrap.classList.add('hidden'); }

  // Cast
  const castWrap = document.getElementById('detail-cast-wrap');
  const castEl   = document.getElementById('detail-cast');
  if (tmdb.cast && tmdb.cast.length) {
    castEl.textContent = tmdb.cast.join(', ');
    castWrap.classList.remove('hidden');
  } else { castWrap.classList.add('hidden'); }

  // Size fallback section
  const sizeWrap = document.getElementById('detail-size-wrap');
  const sizeEl   = document.getElementById('detail-size');
  if (sz && !statParts.find(s => s.includes('📦'))) {
    sizeEl.textContent = sz;
    sizeWrap.classList.remove('hidden');
  } else { sizeWrap.classList.add('hidden'); }

  // Show content
  loading.classList.add('hidden');
  scroll.classList.remove('hidden');
  scroll.scrollTop = 0;
}

function closeDetail() {
  document.getElementById('detail-page').classList.add('hidden');
  document.getElementById('detail-scroll').classList.add('hidden');
  document.getElementById('detail-loading').classList.remove('hidden');
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
    const statusTxt = load.querySelector('.vid-status-txt');
    if (statusTxt) statusTxt.textContent = 'ፊልም እያዘጋጀን ነው…';
    const r = await fetch(
      `/api/stream/start/${filmId}`,
      { headers: _authHeaders() }
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
function _authHeaders() {
  const h = {};
  if (initData) h['X-Init-Data'] = initData;
  if (webToken)  h['Authorization'] = 'Bearer ' + webToken;
  return h;
}

async function api(url) {
  const r = await fetch(url, { headers: _authHeaders() });
  if (r.status === 401) { _handleUnauthorized(); throw new Error('Unauthorized'); }
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

function _handleUnauthorized() {
  if (!tg?.initData) {
    localStorage.removeItem('et_web_token');
    webToken = '';
    showLoginPage();
  }
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

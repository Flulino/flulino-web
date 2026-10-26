/* Flulino Startseite: iPhone, das beim Scrollen durch die App führt. Reines JavaScript, keine Bibliotheken, kein Tracking. */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Kapitel: welcher Bildschirm, wie weit er im iPhone scrollt (px) und wohin gezoomt wird (Bildschirmkoordinaten 390 × 844)
  var CH = [
    { k: 'home',    scroll: 0,   zoom: null,                         glow: 'rgba(59,130,196,.38)' },
    { k: 'wx',      scroll: 105, zoom: { x: 195, y: 449, s: 1.7 },   glow: 'rgba(100,181,255,.32)' },
    { k: 'mb',      scroll: 565, zoom: { x: 195, y: 449, s: 1.85 },  glow: 'rgba(74,222,128,.26)' },
    { k: 'cb',      scroll: 0,   zoom: { x: 195, y: 214, s: 1.75 },  glow: 'rgba(192,132,252,.30)' },
    { k: 'cockpit', scroll: 300, zoom: { x: 195, y: 499, s: 1.55 },  glow: 'rgba(255,107,107,.26)' },
    { k: 'e6b',     scroll: 0,   zoom: { x: 194, y: 336, s: 1.45 },  glow: 'rgba(245,181,71,.24)', wheel: { x: 194, y: 282, r: 176 } },
    { k: 'logbook', scroll: 0,   zoom: { x: 195, y: 294, s: 1.75 },  glow: 'rgba(100,181,255,.32)' }
  ];
  var PW = 418, PH = 872, BZ = 14;

  var story = document.getElementById('story');
  var stage = story.querySelector('.stage');
  var glow = stage.querySelector('.glow');
  var hero = stage.querySelector('.hero-text');
  var wrap = stage.querySelector('.phone-wrap');
  var scrs = {}; stage.querySelectorAll('.scr').forEach(function (el) { scrs[el.dataset.k] = el; });
  var chaps = stage.querySelectorAll('.chap');
  var dots = stage.querySelectorAll('.dots i');

  // Tab-Leiste zeichnen
  var TABS = [
    ['Start', '<path d="M4 11 12 4l8 7v9a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1z"/>'],
    ['Planung', '<path d="m9 4-5 2v14l5-2 6 2 5-2V4l-5 2zM9 4v14M15 6v14"/>'],
    ['Wetter', '<path d="M7 18h10a4 4 0 0 0 0-8 5.5 5.5 0 0 0-10.6 1.5A3.3 3.3 0 0 0 7 18z"/>'],
    ['Pilot', '<rect x="3" y="5" width="18" height="14" rx="2.5"/><circle cx="9" cy="11" r="2.2"/><path d="M5.8 16.5c.6-1.6 1.8-2.4 3.2-2.4s2.6.8 3.2 2.4M14.5 10h4M14.5 13.5h3"/>'],
    ['Mehr', '<circle cx="12" cy="12" r="9"/><circle cx="8" cy="12" r=".9"/><circle cx="12" cy="12" r=".9"/><circle cx="16" cy="12" r=".9"/>']
  ];
  document.querySelectorAll('.tabbar').forEach(function (bar) {
    var a = +bar.dataset.active;
    bar.innerHTML = TABS.map(function (t, i) {
      return '<div class="tab' + (i === a ? ' on' : '') + '"><svg viewBox="0 0 24 24" fill="' + (i === a ? 'currentColor' : 'none') + '" fill-opacity="' + (i === a ? '.25' : '0') + '" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round">' + t[1] + '</svg>' + t[0] + '</div>';
    }).join('');
  });

  // E6B-Rose als drehbarer Ausschnitt des Bildschirmfotos
  CH.forEach(function (c) {
    if (!c.wheel) return;
    var w = scrs[c.k].querySelector('.wheel'), img = scrs[c.k].querySelector('img');
    w.style.cssText += ';left:' + (c.wheel.x - c.wheel.r) + 'px;top:' + (54 + c.wheel.y - c.wheel.r) + 'px;width:' + 2 * c.wheel.r + 'px;height:' + 2 * c.wheel.r + 'px;' +
      'background-image:url(' + img.getAttribute('src') + ');background-size:390px auto;background-position:' + -(c.wheel.x - c.wheel.r) + 'px ' + -(c.wheel.y - c.wheel.r) + 'px;';
    c.wheelEl = w;
  });

  var clamp = function (v, a, b) { return Math.max(a === undefined ? 0 : a, Math.min(b === undefined ? 1 : b, v)); };
  var ease = function (t) { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
  var seg = function (u, a, b) { return ease((u - a) / (b - a)); };

  var W = 0, H = 0, wide = false, base = 1, lastActive = -1;
  function measure() {
    W = stage.clientWidth; H = stage.clientHeight; wide = W >= 900;
    base = wide ? Math.min(H * 0.84 / PH, 1) : Math.min(H * 0.54 / PH, (W - 40) / PW);
  }

  function frame() {
    var r = story.getBoundingClientRect();
    var total = story.offsetHeight - H;
    var p = clamp(-r.top / total) * CH.length;
    var idx = Math.min(CH.length - 1, Math.floor(p));
    var u = idx === CH.length - 1 ? clamp(p - idx, 0, 1) : p - idx;
    var c = CH[idx];

    // Intro: iPhone steigt auf und richtet sich auf
    var intro = idx === 0 ? seg(u, 0, 0.6) : 1;
    var heroOut = idx === 0 ? seg(u, 0.02, 0.38) : 1;
    hero.style.opacity = String(1 - heroOut);
    hero.style.transform = 'translateY(' + (-heroOut * 80) + 'px)';
    hero.style.visibility = heroOut >= 1 ? 'hidden' : 'visible';

    // Bildschirme überblenden
    var fade = idx < CH.length - 1 ? seg(u, 0.86, 1) : 0;
    CH.forEach(function (ch, i) {
      var o = i === idx ? 1 : (i === idx + 1 ? fade : 0);
      scrs[ch.k].style.opacity = String(o);
      scrs[ch.k].style.visibility = o > 0 ? 'visible' : 'hidden';
    });

    // Bildschirminhalt scrollen
    var sc = c.scroll * seg(u, 0.08, 0.34);
    scrs[c.k].querySelector('img').style.transform = 'translateY(' + -sc + 'px)';
    if (c.wheelEl) c.wheelEl.style.transform = 'translateY(' + -sc + 'px) rotate(' + (-150 * seg(u, 0.1, 0.84)) + 'deg)';
    if (CH[idx + 1]) { var n = CH[idx + 1]; scrs[n.k].querySelector('img').style.transform = 'translateY(0)'; if (n.wheelEl) n.wheelEl.style.transform = 'none'; }

    // Zoom auf das Detail
    var k = c.zoom ? seg(u, 0.36, 0.6) * (1 - seg(u, 0.74, 0.88)) : 0;
    var Z = c.zoom ? 1 + (c.zoom.s - 1) * k : 1;
    var s = base * Z;
    var dx = c.zoom ? (c.zoom.x + BZ - PW / 2) : 0, dy = c.zoom ? (c.zoom.y + BZ - PH / 2) : 0;
    var tx = -dx * s * k, ty = -dy * s * k;

    // Position der Bühne
    var cxEnd = wide ? Math.min(W * 0.68, W / 2 + 330) : W / 2;
    var cyEnd = wide ? H * 0.53 : H * 0.34;
    var cx = W / 2 + (cxEnd - W / 2) * intro;
    var cy = cyEnd + (1 - intro) * (wide ? H * 0.62 : H * 0.62);
    var rx = (1 - intro) * 32;
    var sIntro = 0.9 + 0.1 * intro;
    wrap.style.transform = 'translate3d(' + (cx - PW / 2 + tx) + 'px,' + (cy - PH / 2 + ty) + 'px,0) rotateX(' + rx + 'deg) scale(' + (s * sIntro) + ')';

    // Texte
    chaps.forEach(function (el, i) {
      var o = 0;
      if (i === idx) o = (i === 0 ? seg(u, 0.55, 0.7) : seg(u, 0.04, 0.16)) * (idx < CH.length - 1 ? 1 - seg(u, 0.8, 0.92) : 1);
      el.style.opacity = String(o);
      var y = (1 - o) * 30;
      el.style.transform = wide ? 'translateY(calc(-50% + ' + y + 'px))' : 'translateY(' + y + 'px)';
    });

    if (idx !== lastActive) {
      lastActive = idx;
      dots.forEach(function (d, i) { d.classList.toggle('on', i === idx); });
      glow.style.setProperty('--gc', c.glow);
    }
    glow.style.setProperty('--gx', (cx / W * 100) + '%');
    glow.style.setProperty('--gy', (cy / H * 100) + '%');
  }

  var ticking = false;
  function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(function () { ticking = false; frame(); statement(); }); } }

  // Aussage Wort für Wort
  var words = document.querySelector('.words'), st = document.getElementById('statement'), spans = [];
  if (words) {
    var parts = words.textContent.trim().split(/\s+/);
    words.innerHTML = parts.map(function (w, i) { return '<span class="' + (i < 3 ? 'hl' : '') + '">' + w + '</span>'; }).join(' ');
    spans = words.querySelectorAll('span');
  }
  function statement() {
    if (!st) return;
    var r = st.getBoundingClientRect();
    var t = clamp((-r.top + H * 0.15) / (st.offsetHeight - H * 0.9));
    var n = Math.round(t * spans.length);
    spans.forEach(function (s, i) { s.classList.toggle('lit', i < n); });
  }

  // Galerie endlos
  var track = document.querySelector('.track');
  if (track && !reduce) track.innerHTML += track.innerHTML;

  // Funktionen einblenden
  if ('IntersectionObserver' in window && !reduce) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }); }, { rootMargin: '0px 0px -8% 0px' });
    document.querySelectorAll('.feat .feature').forEach(function (f, i) { f.classList.add('reveal'); f.style.transitionDelay = (i % 3) * 70 + 'ms'; io.observe(f); });
  }

  measure(); frame(); statement();
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', function () { measure(); frame(); statement(); });
})();

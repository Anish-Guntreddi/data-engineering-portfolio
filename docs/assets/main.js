/* ============================================================================
   GREEN GATES — editorial interactions
   - code specimen renders with a gentle one-time stagger
   - scroll reveal (IntersectionObserver) for .reveal and .draw
   - verification ledgers: checkmarks draw in (stamp) when in view
   ========================================================================== */
(function () {
  'use strict';
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- 1. Code specimen ---------- */
  var specimen = document.getElementById('specimen');
  var LINES = [
    { t: '$ make run',                              cls: 'pr' },
    { t: '▸ seed raw.*        500 users · 5,691 events', cls: 'gr' },
    { t: '▸ dbt build         70/70 data tests pass',         cls: 'gr' },
    { t: '✓ assert_dau_golden 2024-01-11 → 57   PASS',   cls: 'ok' },
    { t: '✓ assert_revenue    1175.29           PASS',        cls: 'ok' },
    { t: '✓ marts populated · all gates verified',       cls: 'ok' }
  ];
  if (specimen) {
    LINES.forEach(function (l, i) {
      var div = document.createElement('div');
      div.className = 'ln';
      var span = document.createElement('span');
      span.className = l.cls;
      span.textContent = l.t;          // textContent — no markup injection
      div.appendChild(span);
      if (!reduce) {
        div.style.opacity = '0';
        div.style.transform = 'translateY(6px)';
        div.style.transition = 'opacity .45s ease, transform .45s ease';
        div.style.transitionDelay = (0.35 + i * 0.32) + 's';
      }
      specimen.appendChild(div);
    });
    if (!reduce) {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          specimen.querySelectorAll('.ln').forEach(function (d) {
            d.style.opacity = '1';
            d.style.transform = 'none';
          });
        });
      });
    }
  }

  /* ---------- 2. Scroll reveal (.reveal + .draw) ---------- */
  var animated = document.querySelectorAll('.reveal, .draw');
  if (reduce || !('IntersectionObserver' in window)) {
    animated.forEach(function (el) { el.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -8% 0px' });
    animated.forEach(function (el) { io.observe(el); });
  }

  /* ---------- 3. Verification ledgers stamp in ---------- */
  var ledgers = document.querySelectorAll('[data-gates]');
  function stamp(ledger) {
    var gates = ledger.querySelectorAll('.gate');
    gates.forEach(function (g, i) {
      setTimeout(function () { g.classList.add('checked'); }, 220 + i * 260);
    });
  }
  if (reduce || !('IntersectionObserver' in window)) {
    ledgers.forEach(function (l) { l.querySelectorAll('.gate').forEach(function (g) { g.classList.add('checked'); }); });
  } else {
    var gio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        stamp(e.target);
        gio.unobserve(e.target);
      });
    }, { threshold: 0.45 });
    ledgers.forEach(function (l) { gio.observe(l); });
  }

  /* ---------- 4. Active nav link ---------- */
  var links = Array.prototype.slice.call(document.querySelectorAll('.topnav nav a[href^="#"]'));
  var secs = links.map(function (a) { return document.querySelector(a.getAttribute('href')); }).filter(Boolean);
  if (secs.length && 'IntersectionObserver' in window) {
    var nio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          links.forEach(function (a) {
            a.style.color = a.getAttribute('href') === '#' + e.target.id ? 'var(--pine)' : '';
          });
        }
      });
    }, { threshold: 0.5 });
    secs.forEach(function (s) { nio.observe(s); });
  }
})();

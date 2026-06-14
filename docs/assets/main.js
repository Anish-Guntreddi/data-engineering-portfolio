/* ============================================================================
   Green Gates — interactions
   - typewriter terminal that ends on a green PASS
   - infinite pipeline marquee
   - scroll-reveal via IntersectionObserver
   - verification gates that stagger to green when a card enters view
   ========================================================================== */
(function () {
  'use strict';

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- 1. Terminal typewriter ---------- */
  const term = document.getElementById('term');
  const SCRIPT = [
    { t: '$ make run', cls: 'pr', pause: 240 },
    { t: '▸ docker compose up -d postgres', cls: 'mut' },
    { t: '✔ postgres healthy on :5433', cls: 'ok' },
    { t: '▸ python -m generator.load  (seed=42)', cls: 'cy' },
    { t: '  raw.users    500 rows', cls: 'mut' },
    { t: '  raw.events  18,742 rows', cls: 'mut' },
    { t: '  raw.orders   4,310 rows', cls: 'mut' },
    { t: '▸ dbt build --target prod', cls: 'cy' },
    { t: '  staging ......... 3 models  OK', cls: 'mut' },
    { t: '  marts ........... 3 models  OK', cls: 'mut' },
    { t: '  tests ........... 14 passed', cls: 'ok' },
    { t: '✔ assert_dau_golden  2024-01-08 → 211  PASS', cls: 'ok' },
    { t: '', cls: 'mut' },
    { t: 'ALL GATES GREEN — pipeline done.', cls: 'ok' },
  ];

  function renderInstant() {
    term.textContent = '';
    SCRIPT.forEach(function (l) {
      const div = document.createElement('div');
      div.className = 't-line';
      const span = document.createElement('span');
      span.className = l.cls;
      span.textContent = l.t;               // textContent: no markup injection possible
      div.appendChild(span);
      term.appendChild(div);
    });
  }

  function typeLoop() {
    let li = 0;
    function nextLine() {
      if (li >= SCRIPT.length) {
        // hold, then restart for the looping "live" feel
        setTimeout(function () { term.innerHTML = ''; li = 0; nextLine(); }, 4200);
        return;
      }
      const line = SCRIPT[li];
      const div = document.createElement('div');
      div.className = 't-line';
      const span = document.createElement('span');
      span.className = line.cls;
      div.appendChild(span);
      const cur = document.createElement('span');
      cur.className = 'cursor';
      div.appendChild(cur);
      term.appendChild(div);
      // keep the panel scrolled to newest line
      term.scrollTop = term.scrollHeight;

      let ci = 0;
      const text = line.t;
      const speed = line.cls === 'pr' ? 42 : 12;
      (function typeChar() {
        if (ci <= text.length) {
          span.textContent = text.slice(0, ci);
          ci++;
          setTimeout(typeChar, speed);
        } else {
          div.removeChild(cur);
          li++;
          setTimeout(nextLine, line.pause || 160);
        }
      })();
    }
    nextLine();
  }

  if (term) { reduce ? renderInstant() : typeLoop(); }

  /* ---------- 2. Pipeline marquee ---------- */
  const marq = document.getElementById('marq');
  if (marq) {
    const items = [
      ['raw events', 'landing'], ['dbt staging', 'typed'], ['dbt marts', 'tested'],
      ['Dagster DAG', 'scheduled'], ['Redpanda', 'streaming'], ['tumbling windows', 'exact'],
      ['PSI / KS', 'drift'], ['quality score', 'deterministic'], ['golden values', 'asserted'],
      ['docker compose', 'one command'],
    ];
    const appendSet = function () {
      items.forEach(function (p) {
        const span = document.createElement('span');
        span.appendChild(document.createTextNode(p[0] + ' '));
        const b = document.createElement('b');
        b.textContent = p[1];
        span.appendChild(b);
        span.appendChild(document.createTextNode(' ·'));
        marq.appendChild(span);
      });
    };
    appendSet(); appendSet(); // doubled for seamless -50% loop
  }

  /* ---------- 3. Scroll reveal ---------- */
  const reveals = document.querySelectorAll('.reveal');
  if (reduce || !('IntersectionObserver' in window)) {
    reveals.forEach(function (el) { el.classList.add('in'); });
  } else {
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    reveals.forEach(function (el) { io.observe(el); });
  }

  /* ---------- 4. Gate panels stagger to green ---------- */
  const panels = document.querySelectorAll('[data-gates]');
  if (reduce || !('IntersectionObserver' in window)) {
    panels.forEach(function (p) { p.querySelectorAll('.gate').forEach(function (g) { g.classList.add('green'); }); });
  } else {
    const gio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        const gates = e.target.querySelectorAll('.gate');
        gates.forEach(function (g, i) {
          setTimeout(function () { g.classList.add('green'); }, 260 + i * 260);
        });
        gio.unobserve(e.target);
      });
    }, { threshold: 0.4 });
    panels.forEach(function (p) { gio.observe(p); });
  }

  /* ---------- 5. Active nav link on scroll ---------- */
  const navLinks = Array.prototype.slice.call(document.querySelectorAll('.nav-links a[href^="#"]'));
  const sections = navLinks.map(function (a) { return document.querySelector(a.getAttribute('href')); }).filter(Boolean);
  if (sections.length && 'IntersectionObserver' in window) {
    const sio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          navLinks.forEach(function (a) {
            a.style.color = a.getAttribute('href') === '#' + e.target.id ? 'var(--text)' : '';
          });
        }
      });
    }, { threshold: 0.5 });
    sections.forEach(function (s) { sio.observe(s); });
  }
})();

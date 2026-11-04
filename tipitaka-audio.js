/* 🔊 next to the paragraph numbers of the Digha Nikaya (mula_di_01..03).
   Tap 🔊 = plays that paragraph; tap again = stops.  When the paragraph is finished a "▶ ဆက်ဖွင့်" button appears: it plays the following paragraphs one after another
   (as far as the teacher has verified) until a speaker is tapped.  No player box: the browser's audio runs invisibly.
   Recordings: archive.org item tipitaka-audio-myanmar.  Paragraph times: /dhamma/tipitaka-audio/data + the teacher's marks (Firestore tpkaudio/digha, public read). */
(function () {
  var DATA = '/dhamma/tipitaka-audio/data/digha.json';
  var FB = {apiKey: "AIzaSyAZkNjG9WnRVIn1np1uPFvLZtL_M_Q7Vl0", authDomain: "dhamma-songs.firebaseapp.com", projectId: "dhamma-songs", appId: "1:342644793786:web:e9f64de5f0672d46f4bd83"};
  var V = '11.6.1', NK = null, OV = {}, TM = {}, KEY = {}, UP = {}, VER = {}, MISS = {}, IDX = {}, ORD = [], POS = {}, READY = false, loading = null;
  var au = new Audio(), cur = 0, ready = true, curK = null, stopAt = null, cont = false, finished = false;
  au.preload = 'none';
  var st = document.createElement('style');
  st.textContent = '.tpa{border:0;background:none;cursor:pointer;font-size:1rem;padding:0 3px;vertical-align:baseline}.tpa:hover{transform:scale(1.2)}' +
    '.tpa-c{border:1px solid #7b3fb8;background:#fffdf7;color:#7b3fb8;border-radius:8px;padding:0 8px;margin-left:4px;cursor:pointer;font:inherit;font-size:.85rem}' +
    '#tpa-toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:#333;color:#fff;padding:8px 14px;border-radius:10px;z-index:99999;display:none;max-width:90vw}';
  document.head.appendChild(st);
  var toastEl = null, toastT = null;
  function toast(t) { if (!toastEl) { toastEl = document.createElement('div'); toastEl.id = 'tpa-toast'; document.body.appendChild(toastEl) } toastEl.textContent = t; toastEl.style.display = 'block'; clearTimeout(toastT); toastT = setTimeout(function () { toastEl.style.display = 'none' }, 3500) }
  function calc() {
    TM = {};
    NK.groups.forEach(function (g) {
      var t0 = NK.starts[g.fa], t1 = NK.starts[g.fb], cum = 0, W = function (x) { return MISS[x[0] + '|' + x[1]] ? 0 : x[2] }, tot = g.paras.reduce(function (a, x) { return a + W(x) }, 0) || 1;
      var pts = [{c: 0, t: t0}];
      g.paras.forEach(function (x) { var k = x[0] + '|' + x[1]; if (!MISS[k] && OV[k] !== undefined && cum > 0 && OV[k] >= t0 && OV[k] < t1) { var q = pts[pts.length - 1]; if (OV[k] > q.t && cum > q.c) pts.push({c: cum, t: OV[k]}) } cum += W(x) });
      pts.push({c: tot, t: t1}); cum = 0; var j = 0;
      g.paras.forEach(function (x) {
        var k = x[0] + '|' + x[1];
        if (!MISS[k] && OV[k] !== undefined && cum === 0) pts[0].t = OV[k] >= t0 ? OV[k] : t0;
        while (j < pts.length - 2 && cum >= pts[j + 1].c) j++;
        var a = pts[j], b = pts[j + 1]; TM[k] = b.c > a.c ? a.t + (cum - a.c) / (b.c - a.c) * (b.t - a.t) : a.t;
        if (!MISS[k] && OV[k] !== undefined) TM[k] = OV[k]; cum += W(x);
      });
    });
  }
  function load() {
    return loading || (loading = fetch(DATA).then(function (r) { return r.json() }).then(function (d) {
      NK = d; var cn = {};
      NK.groups.forEach(function (g) { g.paras.forEach(function (x) { var k = x[0] + '|' + x[1]; KEY[NK.book[x[0]] + '|' + x[1]] = k; POS[k] = ORD.length; ORD.push(k); IDX[k] = cn[x[0]] = (cn[x[0]] === undefined ? 0 : cn[x[0]] + 1) }) });
      calc();
      import('https://www.gstatic.com/firebasejs/' + V + '/firebase-app.js').then(function (A) {
        return import('https://www.gstatic.com/firebasejs/' + V + '/firebase-firestore.js').then(function (F) {
          var db = F.getFirestore(A.initializeApp(FB, 'tpkread'));
          F.onSnapshot(F.doc(db, 'tpkaudio', NK.id), function (s) {
            var D = s.exists() ? s.data() : {};
            try { OV = JSON.parse(D.j || '{}') } catch (e) { OV = {} }
            try { VER = {}; JSON.parse(D.v || '[]').forEach(function (n) { VER[n] = 1 }) } catch (e) { VER = {} }
            try { MISS = {}; JSON.parse(D.m || '[]').forEach(function (n) { MISS[n] = 1 }) } catch (e) { MISS = {} }
            try { UP = JSON.parse(D.u || '{}') } catch (e) { UP = {} }
            calc(); READY = true;
            document.querySelectorAll('.tpa,.tpa-c').forEach(function (b) { b.remove() }); document.querySelectorAll('[data-tpa]').forEach(function (e) { delete e.dataset.tpa });
            decorate();
          }, function () {});
        });
      }).catch(function () {});
      return NK;
    }));
  }
  var okP = function (k) { var sn = k.split('|')[0]; return !!(VER[sn] || (UP[sn] !== undefined && IDX[k] <= IDX[sn + '|' + UP[sn]])) };
  function fileOf(t) { var f = 0; while (f < NK.dur.length - 1 && NK.starts[f + 1] <= t) f++; return f }
  function endOf(k) { var n = ORD[POS[k] + 1]; if (n === undefined) return NK.starts[NK.dur.length]; return TM[n] + (OV[n] !== undefined ? 1 : 6) }
  function runEnd(k) { var i = POS[k]; while (ORD[i + 1] !== undefined && okP(ORD[i + 1])) i++; return endOf(ORD[i]) }
  function playAt(t, lead) {
    var f = fileOf(t), url = NK.base + NK.pre + '-' + String(f + 1).padStart(3, '0') + '.mp3', off = Math.max(0, t - NK.starts[f] - lead);
    if (cur !== f + 1) { ready = false; au.src = url; cur = f + 1; au.addEventListener('loadedmetadata', function () { au.currentTime = off; ready = true }, {once: true}); au.load() } else au.currentTime = off;
    au.play().catch(function () {});
  }
  function playing() { return !au.paused && !au.ended && stopAt !== null }
  function ui() {
    document.querySelectorAll('.tpa-c').forEach(function (b) { b.remove() });
    document.querySelectorAll('button.tpa').forEach(function (b) {
      var on = playing() && b.dataset.k === curK; b.textContent = on ? '⏹' : '🔊';
      if (!playing() && finished && b.dataset.k === curK) { var c = document.createElement('button'); c.type = 'button'; c.className = 'tpa-c'; c.textContent = '▶ ဆက်ဖွင့်'; c.title = 'နောက်စာပိုဒ်တွေကို ဆက်တိုက်ဖွင့်ရန်'; c.onclick = function (e) { e.preventDefault(); e.stopPropagation(); goOn() }; b.insertAdjacentElement('afterend', c) }
    });
  }
  function stop() { au.pause(); stopAt = null; cont = false; finished = false; ui() }
  function goOn() { if (!curK) return; cont = true; finished = false; stopAt = runEnd(curK); au.play().catch(function () {}); ui() }
  function onTick() {
    if (!ready || stopAt === null || !cur) return;
    var g = NK.starts[cur - 1] + au.currentTime;
    if (g >= stopAt) { au.pause(); stopAt = null; finished = true; ui(); return }
    if (cont) { var i = POS[curK]; while (ORD[i + 1] !== undefined && TM[ORD[i + 1]] <= g && okP(ORD[i + 1])) i++; if (ORD[i] !== curK) { curK = ORD[i]; ui() } }
  }
  au.addEventListener('timeupdate', onTick);
  au.addEventListener('ended', function () { if (cur && cur < NK.dur.length && stopAt !== null && stopAt > NK.starts[cur]) playAt(NK.starts[cur], 0); else { stopAt = null; finished = true; ui() } });
  au.addEventListener('error', function () { stopAt = null; ui(); toast('ဒီအသံဖိုင်ကို မတင်ရသေးပါ (နောက်မှ ပြန်စမ်းပါ)') });
  function book() { return new URLSearchParams(location.search).get('book') || '' }
  function decorate() {
    var b = book(); if (!/^mula_di_0[123]$/.test(b)) return; if (!READY) { load(); return }
    document.querySelectorAll('#tp-content .paranum').forEach(function (el) {
      if (el.dataset.tpa) return; el.dataset.tpa = 1;
      var num = el.textContent.trim().replace(/[။.\s]/g, ''), k = KEY[b + '|' + num]; if (!k || !okP(k)) return;
      if (MISS[k]) { var no = document.createElement('span'); no.className = 'tpa'; no.textContent = '🔇'; no.title = 'ဒီစာပိုဒ်ရဲ့ အသံ မရှိပါ'; no.style.opacity = '.6'; el.insertAdjacentElement('afterend', no); return }
      var btn = document.createElement('button'); btn.type = 'button'; btn.className = 'tpa'; btn.dataset.k = k; btn.textContent = (playing() && curK === k) ? '⏹' : '🔊'; btn.title = 'ဒီစာပိုဒ်ကနေ အသံနားထောင်ရန် (ထပ်နှိပ်ရင် ရပ်မည်)';
      btn.onclick = function (e) {
        e.preventDefault(); e.stopPropagation();
        if (playing() && (cont || curK === k)) { stop(); return }
        curK = k; cont = false; finished = false; stopAt = endOf(k); playAt(TM[k], OV[k] !== undefined ? 2 : 12); ui();
      };
      el.insertAdjacentElement('afterend', btn);
    });
    ui();
  }
  var timer = null;
  new MutationObserver(function () { clearTimeout(timer); timer = setTimeout(decorate, 150) }).observe(document.body, {childList: true, subtree: true});
  decorate();
})();

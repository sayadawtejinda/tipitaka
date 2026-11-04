/* 🔊 next to the paragraph numbers of the Digha Nikaya (mula_di_01..03): plays the recording from that paragraph.
   Recordings: archive.org item tipitaka-audio-myanmar.  Paragraph start times: the Dhamma School page (/dhamma/tipitaka-audio/data) + the teacher's marks (Firestore tpkaudio/digha, public read). */
(function () {
  var DATA = '/dhamma/tipitaka-audio/data/digha.json';
  var FB = {apiKey: "AIzaSyAZkNjG9WnRVIn1np1uPFvLZtL_M_Q7Vl0", authDomain: "dhamma-songs.firebaseapp.com", projectId: "dhamma-songs", appId: "1:342644793786:web:e9f64de5f0672d46f4bd83"};
  var V = '11.6.1', NK = null, VER = {}, READY = false, OV = {}, TM = {}, KEY = {}, au = null, bar = null, cur = 0, loading = null;
  var st = document.createElement('style');
  st.textContent = '.tpa{border:0;background:none;cursor:pointer;font-size:1rem;padding:0 3px;vertical-align:baseline}.tpa:hover{transform:scale(1.2)}' +
    '#tpa-bar{position:fixed;left:8px;right:8px;bottom:8px;z-index:99999;background:#fffdf7;border:2px solid #7b3fb8;border-radius:12px;padding:6px 10px;box-shadow:0 4px 18px rgba(0,0,0,.3);display:none;font-family:inherit}' +
    '#tpa-bar .t{font-size:.85rem;color:#444;display:flex;justify-content:space-between;gap:8px}#tpa-bar audio{width:100%;height:34px}#tpa-bar button{border:1px solid #7b3fb8;background:none;color:#7b3fb8;border-radius:8px;padding:2px 8px;cursor:pointer}';
  document.head.appendChild(st);
  function calc() {
    TM = {};
    NK.groups.forEach(function (g) {
      var t0 = NK.starts[g.fa], t1 = NK.starts[g.fb], cum = 0, tot = g.paras.reduce(function (a, x) { return a + x[2] }, 0) || 1;
      var pts = [{c: 0, t: t0}];
      g.paras.forEach(function (x) { var k = x[0] + '|' + x[1]; if (OV[k] !== undefined && cum > 0 && OV[k] >= t0 && OV[k] < t1) { var q = pts[pts.length - 1]; if (OV[k] > q.t && cum > q.c) pts.push({c: cum, t: OV[k]}) } cum += x[2] });
      pts.push({c: tot, t: t1}); cum = 0; var j = 0;
      g.paras.forEach(function (x) {
        var k = x[0] + '|' + x[1];
        if (OV[k] !== undefined && cum === 0) pts[0].t = OV[k] >= t0 ? OV[k] : t0;
        while (j < pts.length - 2 && cum >= pts[j + 1].c) j++;
        var a = pts[j], b = pts[j + 1]; TM[k] = b.c > a.c ? a.t + (cum - a.c) / (b.c - a.c) * (b.t - a.t) : a.t;
        if (OV[k] !== undefined) TM[k] = OV[k]; cum += x[2];
      });
    });
  }
  function load() {
    return loading || (loading = fetch(DATA).then(function (r) { return r.json() }).then(function (d) {
      NK = d; NK.groups.forEach(function (g) { g.paras.forEach(function (x) { KEY[NK.book[x[0]] + '|' + x[1]] = x[0] + '|' + x[1] }) });
      calc();
      import('https://www.gstatic.com/firebasejs/' + V + '/firebase-app.js').then(function (A) {
        return import('https://www.gstatic.com/firebasejs/' + V + '/firebase-firestore.js').then(function (F) {
          var db = F.getFirestore(A.initializeApp(FB, 'tpkread'));
          F.onSnapshot(F.doc(db, 'tpkaudio', NK.id), function (s) { try { OV = s.exists() ? JSON.parse(s.data().j || '{}') : {} } catch (e) { OV = {} } try { VER = {}; (s.exists() ? JSON.parse(s.data().v || '[]') : []).forEach(function (n) { VER[n] = 1 }) } catch (e) { VER = {} } calc(); READY = true; document.querySelectorAll('.tpa').forEach(function (b) { b.remove() }); document.querySelectorAll('[data-tpa]').forEach(function (e) { delete e.dataset.tpa }); decorate() }, function () {});
        });
      }).catch(function () {});
      return NK;
    }));
  }
  function fileOf(t) { var f = 0; while (f < NK.dur.length - 1 && NK.starts[f + 1] <= t) f++; return f }
  function ensureBar() {
    if (bar) return;
    bar = document.createElement('div'); bar.id = 'tpa-bar';
    bar.innerHTML = '<div class="t"><span id="tpa-t"></span><button type="button" id="tpa-x">✕</button></div><audio controls></audio>';
    document.body.appendChild(bar); au = bar.querySelector('audio');
    bar.querySelector('#tpa-x').onclick = function () { au.pause(); bar.style.display = 'none' };
    au.addEventListener('error', function () { document.getElementById('tpa-t').textContent += ' — ဒီအသံဖိုင်ကို မတင်ရသေးပါ (နောက်မှ ပြန်စမ်းပါ)' });
    au.addEventListener('ended', function () { if (cur && cur < NK.dur.length) playAt(NK.starts[cur], 0) });
  }
  function playAt(t, lead) {
    var f = fileOf(t), url = NK.base + NK.pre + '-' + String(f + 1).padStart(3, '0') + '.mp3', off = Math.max(0, t - NK.starts[f] - lead);
    if (cur !== f + 1) { au.src = url; cur = f + 1; au.addEventListener('loadedmetadata', function () { au.currentTime = off }, {once: true}); au.load() } else au.currentTime = off;
    au.play().catch(function () {});
  }
  function book() { return new URLSearchParams(location.search).get('book') || '' }
  function decorate() {
    var b = book(); if (!/^mula_di_0[123]$/.test(b)) return; if (!READY) { load(); return }
    document.querySelectorAll('#tp-content .paranum').forEach(function (el) {
      if (el.dataset.tpa) return; el.dataset.tpa = 1;
      var num = el.textContent.trim().replace(/[။.\s]/g, '');
      load().then(function () {
        var k = KEY[b + '|' + num]; if (!k || !VER[k.split('|')[0]]) return;
        var btn = document.createElement('button'); btn.type = 'button'; btn.className = 'tpa'; btn.textContent = '🔊'; btn.title = 'ဒီစာပိုဒ်ကနေ အသံနားထောင်ရန်';
        btn.onclick = function (e) { e.preventDefault(); e.stopPropagation(); ensureBar(); bar.style.display = 'block'; document.getElementById('tpa-t').textContent = '🔊 စာပိုဒ် ' + num + ' · ' + NK.suttas[k.split('|')[0]];
          playAt(TM[k], OV[k] !== undefined ? 2 : 12) };
        el.insertAdjacentElement('afterend', btn);
      });
    });
  }
  var timer = null;
  new MutationObserver(function () { clearTimeout(timer); timer = setTimeout(decorate, 150) }).observe(document.body, {childList: true, subtree: true});
  decorate();
})();

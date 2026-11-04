/* 🔊 next to the paragraph numbers of the books that have a recording (Digha, Majjhima, Samyutta, Anguttara, Khuddaka, Abhidhamma): tap = plays that paragraph only, tap again = stops.
   The 📽 Slide button beside the page citation at the top (#tp-meta) starts the slide view from the first verified paragraph of the page: the paragraphs are read one after another and their text is shown.
   Recordings: archive.org item tipitaka-audio-myanmar.  Paragraph times: /dhamma/tipitaka-audio/data + the teacher's marks (Firestore tpkaudio/digha, public read). */
(function () {
  var DATA = '/dhamma/tipitaka-audio/data/', TEXTC = {}, slide = null, slideFz = 1.7, slideK = null, slideR = false, slideSent = [];
  // which recording set reads which book
  function setOf(b) {
    if (/^mula_di_0[123]$/.test(b)) return 'digha'; if (/^mula_ma_/.test(b)) return 'mn'; if (/^mula_sa_/.test(b)) return 'sn'; if (/^mula_an_/.test(b)) return 'an'; if (/^mula_ku_/.test(b)) return 'kn';
    var m = /^mula_bi_0([1-5])$/.exec(b); if (m) return 'ab' + m[1]; if (/^mula_bi_06_/.test(b)) return 'ab6'; if (/^mula_bi_07_/.test(b)) return 'pt'; return null;
  }
  var lab = function (p) { return String(p).replace(/_\d+$/, '') }, ST = {}, curSet = null, NUM = {};
  var FB = {apiKey: "AIzaSyAZkNjG9WnRVIn1np1uPFvLZtL_M_Q7Vl0", authDomain: "dhamma-songs.firebaseapp.com", projectId: "dhamma-songs", appId: "1:342644793786:web:e9f64de5f0672d46f4bd83"};
  var V = '11.6.1', NK = null, OV = {}, TM = {}, UP = {}, VER = {}, MISS = {}, IDX = {}, ORD = [], POS = {}, READY = false;
  var audioSet = null, au = new Audio(), cur = 0, ready = true, curK = null, stopAt = null, cont = false, finished = false;
  au.preload = 'none';
  var st = document.createElement('style');
  st.textContent = '.tpa{border:0;background:none;cursor:pointer;font-size:1rem;padding:0 3px;vertical-align:baseline}.tpa:hover{transform:scale(1.2)}' +
    '.tpa-sl{border:1px solid #7b3fb8;background:#fffdf7;color:#7b3fb8;border-radius:999px;cursor:pointer;font:inherit;font-size:.72rem;padding:0 7px;margin:0 6px;vertical-align:baseline;line-height:1.5}' +
    '.tpa-c{border:1px solid #7b3fb8;background:#fffdf7;color:#7b3fb8;border-radius:8px;padding:0 8px;margin-left:4px;cursor:pointer;font:inherit;font-size:.85rem}' +
    '#tpa-slide{position:fixed;inset:0;z-index:99998;background:#fffdf7;color:#2a2118;display:flex;flex-direction:column;font-family:inherit}#tpa-slide .hd{padding:10px 14px;border-bottom:1px solid #e3d8c8;display:flex;justify-content:space-between;gap:8px;align-items:center;color:#7a6a58;font-size:.9rem}' +
    '#tpa-slide .bd{flex:1;overflow:auto;padding:18px 18px 30px;max-width:900px;margin:0 auto;width:100%;line-height:2.1;white-space:pre-wrap}#tpa-slide .s{border-radius:8px;padding:0 3px;opacity:.45;transition:.25s}#tpa-slide .s.on{opacity:1;background:#ffe9a8}#tpa-slide .s.hh{display:inline-block;font-weight:700;color:#7b3fb8;text-align:center;width:100%}' +
    '#tpa-slide .ft{display:flex;gap:8px;justify-content:center;padding:10px;border-top:1px solid #e3d8c8;flex-wrap:wrap}#tpa-slide button{border:1px solid #7b3fb8;background:#fff;color:#7b3fb8;border-radius:10px;padding:6px 14px;cursor:pointer;font:inherit}#tpa-slide button.pri{background:#7b3fb8;color:#fff}' +
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
  function use(id) { var s = ST[id]; if (!s || !s.ready) return false; NK = s.NK; OV = s.OV; TM = s.TM; UP = s.UP; VER = s.VER; MISS = s.MISS; IDX = s.IDX; ORD = s.ORD; POS = s.POS; NUM = s.NUM; READY = true; return true }
  function load(id) {
    if (ST[id]) return ST[id].p;
    var s = ST[id] = {ready: false, OV: {}, UP: {}, VER: {}, MISS: {}};
    s.p = fetch(DATA + id + '.json').then(function (r) { return r.json() }).then(function (d) {
      s.NK = d; s.TM = {}; s.IDX = {}; s.ORD = []; s.POS = {}; s.NUM = {}; var cn = {};
      d.groups.forEach(function (g) { g.paras.forEach(function (x) { var k = x[0] + '|' + x[1]; s.POS[k] = s.ORD.length; s.ORD.push(k); s.IDX[k] = cn[x[0]] = (cn[x[0]] === undefined ? 0 : cn[x[0]] + 1); var nk = d.book[x[0]] + '|' + lab(x[1]); (s.NUM[nk] = s.NUM[nk] || []).push([k, typeof x[3] === 'number' ? x[3] : null]) }) });
      s.ready = true; var keep = curSet; use(id); calc(); s.TM = TM; if (keep && keep !== id) use(keep);
      import('https://www.gstatic.com/firebasejs/' + V + '/firebase-app.js').then(function (A) {
        return import('https://www.gstatic.com/firebasejs/' + V + '/firebase-firestore.js').then(function (F) {
          var app; try { app = A.getApp('tpkread') } catch (e) { app = A.initializeApp(FB, 'tpkread') }
          var db = F.getFirestore(app);
          F.onSnapshot(F.doc(db, 'tpkaudio', id), function (sn) {
            var D = sn.exists() ? sn.data() : {};
            try { s.OV = JSON.parse(D.j || '{}') } catch (e) { s.OV = {} }
            try { s.VER = {}; JSON.parse(D.v || '[]').forEach(function (n) { s.VER[n] = 1 }) } catch (e) { s.VER = {} }
            try { s.MISS = {}; JSON.parse(D.m || '[]').forEach(function (n) { s.MISS[n] = 1 }) } catch (e) { s.MISS = {} }
            try { s.UP = JSON.parse(D.u || '{}') } catch (e) { s.UP = {} }
            s.snap = true; var keep2 = curSet; use(id); calc(); s.TM = TM; if (keep2 && keep2 !== id) use(keep2);
            document.querySelectorAll('.tpa,.tpa-c,.tpa-top,.tpa-sl').forEach(function (b) { b.remove() }); document.querySelectorAll('[data-tpa]').forEach(function (e) { delete e.dataset.tpa });
            decorate();
          }, function () {});
        });
      }).catch(function () {});
      return d;
    });
    return s.p;
  }
  function playingNow() { return au && !au.paused }
  var okP = function (k) { var sn = k.split('|')[0]; return !!(VER[sn] || (UP[sn] !== undefined && IDX[k] <= IDX[sn + '|' + UP[sn]])) };
  function fileOf(t) { var f = 0; while (f < NK.dur.length - 1 && NK.starts[f + 1] <= t) f++; return f }
  function endOf(k) { var n = ORD[POS[k] + 1]; if (n === undefined) return NK.starts[NK.dur.length]; return TM[n] + (OV[n] !== undefined ? 1 : 6) }
  function runEnd(k) { var i = POS[k]; while (ORD[i + 1] !== undefined && okP(ORD[i + 1])) i++; return endOf(ORD[i]) }
  function playAt(t, lead) {
    var f = fileOf(t), url = NK.base + (NK.files ? NK.files[f] : NK.pre + '-' + String(f + 1).padStart(3, '0') + '.mp3'), off = Math.max(0, t - NK.starts[f] - lead);
    if (cur !== f + 1 || audioSet !== curSet) { audioSet = curSet; ready = false; au.src = url; cur = f + 1; au.addEventListener('loadedmetadata', function () { au.currentTime = off; ready = true }, {once: true}); au.load() } else au.currentTime = off;
    au.play().catch(function () {});
  }
  function playing() { return !au.paused && !au.ended && stopAt !== null }
  function ui() {
    if (cont && stopAt !== null) { openSlide(); paintSlide() } else closeSlide();
    document.querySelectorAll('.tpa-c').forEach(function (b) { b.remove() });
    document.querySelectorAll('button.tpa').forEach(function (b) {
      var on = playing() && b.dataset.k === curK; b.textContent = on ? '⏹' : '🔊';
    });
  }
  // ---- slide view (while the paragraphs play one after another): the text of the paragraph that is being read, the sentence in the reading position lit
  function gtime() { return cur ? NK.starts[cur - 1] + au.currentTime : 0 }
  function esc(s) { return s.replace(/[&<>]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c] }) }
  function textFile(k) { var b = NK.book[k.split('|')[0]]; return NK.id === 'digha' ? DATA + 'digha_text.json' : DATA + 'txt/' + b + '.json' }
  function loadText(k) { var f = textFile(k); return TEXTC[f] || (TEXTC[f] = fetch(f).then(function (r) { return r.json() })) }
  function openSlide() {
    if (slide) return;
    slide = document.createElement('div'); slide.id = 'tpa-slide'; slideK = null;
    slide.innerHTML = '<div class="hd"><span id="tpa-sh"></span><span><button type="button" data-a="-1">A−</button> <button type="button" data-a="1">A+</button></span></div><div class="bd"></div><div class="ft"><button type="button" data-c="prev" title="အရင်ပိုဒ်">⏮</button><button type="button" class="pri" data-c="pp">⏸</button><button type="button" data-c="next" title="နောက်ပိုဒ်">⏭</button><button type="button" data-c="close" title="ပိတ်ရန်">✕</button></div>';
    document.body.appendChild(slide); slide.querySelector('.bd').style.fontSize = slideFz + 'rem';
    slide.onclick = function (e) {
      var a = e.target.dataset.a, c = e.target.dataset.c;
      if (a) { slideFz = Math.max(1, Math.min(3, slideFz + (+a) * .2)); slide.querySelector('.bd').style.fontSize = slideFz + 'rem'; return }
      if (c === 'close') { stop(); return }
      if (c === 'pp') { if (au.paused) au.play().catch(function () {}); else au.pause(); hilite(); return }
      if (c === 'prev' || c === 'next') { var i = POS[curK] + (c === 'next' ? 1 : -1); if (ORD[i] !== undefined && okP(ORD[i])) { curK = ORD[i]; playAt(TM[curK], 0); ui() } }
    };
  }
  function closeSlide() { if (slide) { slide.remove(); slide = null; slideK = null } }
  function paintSlide() {
    if (!slide || !curK) return;
    var kk = curK; loadText(kk).then(function (TEXT) {
      if (!slide || kk !== curK) return;
      var rom = !!(window.tpRomanApi && window.tpRomanApi.is()), cv = function (x) { return rom ? window.tpRomanApi.conv(x) : x };
      if (slideK !== curK || slideR !== rom) {
        slideR = rom;
        slideK = curK; var hd = TEXT[curK + '^'] || [[], []], body = (TEXT[curK] || '').split(/(?<=[။\n])/).filter(function (x) { return x.trim() });
        var parts = hd[0].concat(body, hd[1]), nH = hd[0].length, nB = body.length;       // headings before and the closing line after the paragraph are read aloud too
        slideSent = parts.map(function (x) { return x.length });
        slide.querySelector('#tpa-sh').textContent = '🔊 ' + cv(NK.suttas[curK.split('|')[0]]) + ' · ¶' + cv(lab(curK.split('|')[1]));
        slide.querySelector('.bd').innerHTML = parts.map(function (x, i) { var h = i < nH || i >= nH + nB; return '<span class="s' + (h ? ' hh' : '') + '">' + esc(cv(x)) + '</span>' + (h ? '<br>' : '') }).join('');
        slide.querySelector('.bd').scrollTop = 0;
      }
      hilite();
    });
  }
  function hilite() {
    if (!slide || !slideSent.length || !curK) return;
    var s = TM[curK], nx = ORD[POS[curK] + 1], e = nx !== undefined ? TM[nx] : NK.starts[NK.dur.length], f = e > s ? Math.max(0, Math.min(.999, (gtime() - s) / (e - s))) : 0;
    var tot = slideSent.reduce(function (a, b) { return a + b }, 0), acc = 0, idx = slideSent.length - 1;
    for (var i = 0; i < slideSent.length; i++) { acc += slideSent[i]; if (acc / tot > f) { idx = i; break } }
    var on = null; slide.querySelectorAll('.s').forEach(function (el, i) { var o = i === idx; if (o !== el.classList.contains('on')) el.classList.toggle('on', o); if (o) on = el });
    if (on) { var bd = slide.querySelector('.bd'), r = on.getBoundingClientRect(), b = bd.getBoundingClientRect(); if (r.bottom > b.bottom - 40 || r.top < b.top + 20) bd.scrollTop += r.top - b.top - b.height / 3 }
    var pp = slide.querySelector('[data-c="pp"]'); if (pp) pp.textContent = au.paused ? '▶' : '⏸';
  }
  function stop() { au.pause(); stopAt = null; cont = false; finished = false; ui() }
  function startSlide(k) { curK = k; cont = true; finished = false; stopAt = runEnd(k); playAt(TM[k], 2); ui() }      // slide: start right at the paragraph (2 s ahead) so the text and the voice are the same paragraph
  function goOn() { if (!curK) return; cont = true; finished = false; stopAt = runEnd(curK); au.play().catch(function () {}); ui() }
  function onTick() {
    if (!ready || stopAt === null || !cur) return;
    var g = NK.starts[cur - 1] + au.currentTime;
    if (g >= stopAt) { var wasCont = cont; au.pause(); stopAt = null; cont = false; finished = true; ui(); if (wasCont) toast('ဒီနေရာအထိပဲ အသံ အတည်ပြုပြီးသေးပါသည် — နောက်ပိုင်းကို ဆရာ စစ်ပြီးမှ ဆက်နားထောင်နိုင်ပါမည်'); return }
    if (cont) { var lo = 0, hi = ORD.length - 1; while (lo < hi) { var mid = (lo + hi + 1) >> 1; if (TM[ORD[mid]] <= g) lo = mid; else hi = mid - 1 } var nk = ORD[lo]; if (nk !== curK && okP(nk) && !(POS[nk] < POS[curK] && g < TM[curK])) { curK = nk; ui() } else hilite() }      // (the 2 s lead-in before the first paragraph still belongs to the paragraph that was asked for)
  }
  au.addEventListener('timeupdate', onTick);
  au.addEventListener('ended', function () { if (cur && cur < NK.dur.length && stopAt !== null && stopAt > NK.starts[cur]) playAt(NK.starts[cur], 0); else { stopAt = null; finished = true; ui() } });
  au.addEventListener('error', function () { stopAt = null; ui(); toast('ဒီအသံဖိုင်ကို မတင်ရသေးပါ (နောက်မှ ပြန်စမ်းပါ)') });
  function book() { return new URLSearchParams(location.search).get('book') || '' }
  function pageNo() { var p = new URLSearchParams(location.search).get('page'); return p ? +p : null }
  function pick(cands, page, seen) {
    if (!cands) return null; if (cands.length === 1) return cands[0][0];
    var best = 1e9, list = [];
    cands.forEach(function (c) { var d = c[1] === null || page === null ? 0 : Math.abs(c[1] - page); if (d < best) { best = d; list = [c] } else if (d === best) list.push(c) });
    return (list[Math.min(seen, list.length - 1)] || cands[0])[0];
  }
  function decorate() {
    var b = book(), sid = setOf(b); if (!sid) return;
    if (!ST[sid] || !ST[sid].ready || !ST[sid].snap) { load(sid); return }
    if (curSet !== sid) { if (curSet && (cont || stopAt !== null || playingNow())) stop(); curSet = sid }
    use(sid);
    var seenL = {}, pg0 = pageNo();
    document.querySelectorAll('#tp-content .paranum').forEach(function (el) {
      if (el.dataset.tpa) return; el.dataset.tpa = 1;
      var pg = pg0 === null ? null : (el.closest('.tp-prev-page') ? pg0 - 1 : el.closest('.tp-next-page') ? pg0 + 1 : pg0);      // the reader stitches the previous / next page around the current one
      var num = el.textContent.trim().replace(/[။.\s]/g, '').replace(/[0-9]/g, function (d) { return '၀၁၂၃၄၅၆၇၈၉'[d] }), sk = num + '@' + pg, n = seenL[sk] = (seenL[sk] === undefined ? 0 : seenL[sk] + 1), k = pick(NUM[b + '|' + num], pg, n); if (!k || !okP(k)) return;
      if (MISS[k]) { var no = document.createElement('span'); no.className = 'tpa'; no.textContent = '🔇'; no.title = 'ဒီစာပိုဒ်ရဲ့ အသံ မရှိပါ'; no.style.opacity = '.6'; el.insertAdjacentElement('afterend', no); return }
      var btn = document.createElement('button'); btn.type = 'button'; btn.className = 'tpa'; btn.dataset.k = k; btn.textContent = (playing() && curK === k) ? '⏹' : '🔊'; btn.title = 'ဒီစာပိုဒ်ကနေ အသံနားထောင်ရန် (ထပ်နှိပ်ရင် ရပ်မည်)';
      btn.onclick = function (e) {
        e.preventDefault(); e.stopPropagation();
        if (playing() && (cont || curK === k)) { stop(); return }
        curK = k; cont = false; finished = false; stopAt = endOf(k); playAt(TM[k], OV[k] !== undefined ? 2 : 12); ui();
      };
      el.insertAdjacentElement('afterend', btn);
    });
    var meta = document.getElementById('tp-meta'), first = document.querySelector('#tp-current-page button.tpa[data-k]');
    if (meta && first && !meta.querySelector('.tpa-sl')) {
      var sl = document.createElement('button'); sl.type = 'button'; sl.className = 'tpa-sl'; sl.textContent = '📽 Slide'; sl.title = 'ဒီစာမျက်နှာရဲ့ ပထမစာပိုဒ်ကနေ စာသားပြပြီး ဆက်တိုက် ဖတ်ပေးမည်';
      sl.onclick = function (e) { e.preventDefault(); e.stopPropagation(); var f = document.querySelector('#tp-current-page button.tpa[data-k]'); if (!f) return; if (cont && stopAt !== null) stop(); else startSlide(f.dataset.k) };
      meta.appendChild(sl);
    }
    ui();
  }
  var timer = null;
  new MutationObserver(function () { clearTimeout(timer); timer = setTimeout(decorate, 150) }).observe(document.body, {childList: true, subtree: true});
  decorate();
})();

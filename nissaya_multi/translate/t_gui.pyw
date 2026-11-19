# -*- coding: utf-8 -*-
"""Pali -> Burmese translation tool (like run_tool): ① file for the Gemini 'Pali Translate AI' app  ② Gemini's answers are taken from Downloads  ③ translated book out."""
import os, subprocess, sys, threading, tkinter as tk
from tkinter import ttk, messagebox
HERE = os.path.dirname(os.path.abspath(__file__)); NSY = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(NSY, 'scripts'))
# every helper program (git ...) started from here runs WITHOUT a console window (otherwise a black window flashes open and shut every few seconds)
class _NoWinPopen(subprocess.Popen):
    def __init__(self, *a, **k):
        if os.name == 'nt': k.setdefault('creationflags', 0x08000000)
        super().__init__(*a, **k)
subprocess.Popen = _NoWinPopen
import t_core, m_tool

root = tk.Tk(); root.title('ပါဠိ မြန်မာပြန် ကိရိယာ'); root.geometry('900x640')
f = ttk.Frame(root, padding=10); f.pack(fill='both', expand=True); f.columnconfigure(1, weight=1); f.rowconfigure(6, weight=1)
import glob, json
TIPI = os.path.dirname(NSY)
import m_status
def published(): return m_status.on_web_set()          # one shared rule for run_tool and run_translate (scripts/m_status.py)
STATE = os.path.join(HERE, 'gui_state.json')
def load_state():
    try: return json.load(open(STATE, encoding='utf-8'))
    except Exception: return {}
def save_state(**kw):
    st = load_state(); st.update(kw)
    try: json.dump(st, open(STATE, 'w', encoding='utf-8'))
    except Exception: pass
hidepub = tk.BooleanVar(value=load_state().get('hide_pub', True))
lang_var = tk.StringVar(value=load_state().get('lang', 'my'))          # my = Pali -> Burmese;  vi / en = the Burmese translation (+ the Pali page) -> Vietnamese / English
LANG_NAME = {'my': 'မြန်မာ', 'vi': 'ဗီယက်နမ်', 'en': 'အင်္ဂလိပ်'}
def _json(path, default):
    try: return json.load(open(path, encoding='utf-8'))
    except Exception: return default
gemini_done = m_status.gemini_done          # the nissaya of the sheet is completely checked by Gemini (same rule as run_tool)
def lang_on_web(n, L):
    """the Vietnamese / English of sheet n is on the web (data/translations_<L>/): every Pali page that has a Burmese translation is in the sheet's web file"""
    idx = _json(os.path.join(TIPI, 'data', 'translations_' + L, 'index.json'), {})
    my = {k for k, v in t_core.load_translations(n).items() if v.strip()}
    if not my or not isinstance(idx, dict): return False
    have = set()
    for ents in idx.values():
        for e in ents:
            if n in (e.get('sheets') or [e.get('sheet')]): have.update(int(k) for k in _json(os.path.join(TIPI, 'data', 'translations_' + L, e['file']), {}))
    return my <= have
def translated_here(n, books, tri):
    """the translation on the web covers EVERY Pali page of this sheet (a Pali book made of two sheets - e.g. 117 = Pali 1-135, 118 = Pali 136-254 - is not finished when only the first sheet is translated)"""
    if not tri: return False
    try: P = json.load(open(os.path.join(NSY, 'paired', '%03d.json' % n), encoding='utf-8'))['ppmap']
    except Exception: return False
    for x in books:
        if x not in tri: return False
        if isinstance(tri, list): continue                                       # old index form (a list of books): the whole book
        have = set()
        for e in tri[x]:
            d = _json(os.path.join(TIPI, 'data', 'nissaya_translations', e['file']), {}); have.update(int(k) for k in d)
        need = {int(k.split('|')[1]) for k in P if k.split('|')[0] == x}
        if not need or not need <= have: return False
    return True
def get_sheets(keep=None):
    keep = keep if keep is not None else load_state().get('sheet')     # the book chosen / published last stays in the list (even when it would be hidden)
    L = lang_var.get()
    if L in ('vi', 'en'):               # Vietnamese / English: the sheets that already have a Burmese translation (gold/tr_NNN.json); a sheet finished in the language is hidden when the box is ticked
        out = []
        for n, t in m_tool.list_sheets():
            if not os.path.exists(os.path.join(t_core.GOLD, 'tr_%03d.json' % n)): continue
            tot, got = t_core.lang_progress(n, L)
            if not tot: continue
            web = lang_on_web(n, L)
            if n != keep and hidepub.get() and web: continue                 # the ticked box: a sheet whose Vietnamese / English is ON THE WEB (all its Burmese-translated pages) is hidden
            out.append((n, '%s   [%s %d/%d%s]' % (t, LANG_NAME[L], got, tot, ' · web ✓' if web else '')))
        return out
    """books of run_tool that are on the web, WITHOUT the books that already have a Myanmar translation Split View (data/mm_split: not translated again) and (when ticked) without the books whose translation is already on the web"""
    pub = published()
    mm = set(_json(os.path.join(TIPI, 'data', 'mm_split', 'index.json'), {}))
    tri = _json(os.path.join(TIPI, 'data', 'nissaya_translations', 'index.json'), []) if hidepub.get() else []
    bks = {r['n']: (r.get('final') or {}).get('books') or [] for r in _json(os.path.join(NSY, 'catalog.json'), [])}
    out = []
    for n, t in m_tool.list_sheets():
        if n not in pub: continue
        if not gemini_done(n): continue                    # nissaya not (completely) checked by Gemini yet: not offered for translation
        b = bks.get(n) or []
        if n != keep and b and (all(x in mm for x in b) or translated_here(n, b, tri)): continue
        out.append((n, t))
    return out
sheets = get_sheets()
ttk.Label(f, text='စာအုပ်', font=('', 11, 'bold')).grid(row=0, column=0, sticky='w')
cb = ttk.Combobox(f, values=[t for n, t in sheets], state='readonly'); cb.grid(row=0, column=1, sticky='we')
_last = load_state().get('sheet')                       # the book chosen last time is chosen again
for _i, (_n, _t) in enumerate(sheets):
    if _n == _last: cb.current(_i)
cb.bind('<<ComboboxSelected>>', lambda e: save_state(sheet=sheets[cb.current()][0]))
def _toggle_hide():
    save_state(hide_pub=bool(hidepub.get())); refresh_books(force=True)
_hide_cb = ttk.Checkbutton(f, text='✅ web ပေါ်တင်ပြီးသော မြန်မာပြန် စာအုပ်များ ဖျောက်', variable=hidepub, command=_toggle_hide); _hide_cb.grid(row=0, column=2, sticky='w', padx=6)
if lang_var.get() in ('vi', 'en'): _hide_cb.config(text='✅ web ပေါ်တင်ပြီးသော %sပြန် စာအုပ်များ ဖျောက်' % LANG_NAME[lang_var.get()])
def _lang_changed(*_):
    save_state(lang=lang_var.get()); _hide_cb.config(text=('✅ web ပေါ်တင်ပြီးသော မြန်မာပြန် စာအုပ်များ ဖျောက်' if lang_var.get() == 'my' else '✅ web ပေါ်တင်ပြီးသော %sပြန် စာအုပ်များ ဖျောက်' % LANG_NAME[lang_var.get()])); refresh_books(force=True)
ttk.Label(f, text='ဘာသာပြန်မည့်ဘာသာ').grid(row=0, column=3, sticky='e', padx=(10, 2))
_lc = ttk.Combobox(f, state='readonly', width=12, values=[LANG_NAME['my'], LANG_NAME['vi'], LANG_NAME['en']]); _lc.grid(row=0, column=4, sticky='w')
_lc.current(['my', 'vi', 'en'].index(lang_var.get()) if lang_var.get() in ('my', 'vi', 'en') else 0)
def _lc_pick(e=None):
    lang_var.set(['my', 'vi', 'en'][_lc.current()]); _lang_changed()
_lc.bind('<<ComboboxSelected>>', _lc_pick)
def refresh_books(force=False):        # a book that run_tool publishes later appears here by itself (checked every few seconds); the chosen book stays chosen
    global sheets
    keep = sheets[cb.current()][0] if cb.current() >= 0 else None
    new = get_sheets(keep)
    if not force and [n for n, t in new] == [n for n, t in sheets]: return
    sheets = new; cb['values'] = [t for n, t in sheets]
    for i, (n, t) in enumerate(sheets):
        if n == keep: cb.current(i)
    say('📚 စာအုပ်စာရင်း ပြောင်းသည် — %s စာအုပ် %d အုပ်' % ('web တင်ပြီး' if lang_var.get() == 'my' else LANG_NAME[lang_var.get()] + 'ပြန်ရန်', len(sheets)))
r = ttk.Frame(f); r.grid(row=1, column=0, columnspan=2, sticky='w', pady=6)
ttk.Label(r, text='စာအုပ်တစ်အုပ်လုံး ထုတ်မည်။    အစုတစ်စု စာလုံးရေ အများဆုံး').pack(side='left'); mc = ttk.Entry(r, width=6); mc.pack(side='left', padx=3); mc.insert(0, '10000')
ttk.Label(r, text='   ဖိုင်တစ်ခုမှာ အစု').pack(side='left'); ns = ttk.Entry(r, width=3); ns.pack(side='left', padx=3); ns.insert(0, '10')
redo = tk.BooleanVar(value=False)
ttk.Checkbutton(f, text='မြန်မာပြန်ပြီးသော ပါဠိမျက်နှာကိုပါ ပြန်ထုတ် (မခြစ်လျှင် မပြန်ရသေးသည်များကိုသာ စုထုတ်)', variable=redo).grid(row=5, column=0, columnspan=2, sticky='w')
raw = tk.BooleanVar(value=False)
ttk.Checkbutton(f, text='Gemini မစစ်ရသေးသော နိဿယစာမျက်နှာကို OCR စာဖြင့် ထည့် (မခြစ်လျှင် စစ်ပြီးသော နိဿယသာ ယူ၊ မစစ်ရသေးလျှင် ထိုပါဠိမျက်နှာကို ချန်)', variable=raw).grid(row=2, column=0, columnspan=2, sticky='w')
bf = ttk.Frame(f); bf.grid(row=3, column=0, columnspan=2, sticky='w', pady=6)
log = tk.Text(f, height=20); log.grid(row=6, column=0, columnspan=2, sticky='nsew')
def say(s): root.after(0, lambda: (log.insert('end', str(s) + chr(10)), log.see('end')))
def sel():
    if cb.current() < 0:
        messagebox.showerror('စာအုပ် မရွေးရသေးပါ', 'အပေါ်က "စာအုပ်" ကွက်မှာ အရင်ရွေးပါ။'); raise RuntimeError('no book')
    return sheets[cb.current()][0]


def work1(n, m, k):
    try:
        L = lang_var.get()
        if L in ('vi', 'en'):
            out, files = t_core.build_lang(n, L, m, k, say, redo=redo.get())
            say('✔ ဖိုင် %d ခု ထွက်ပါပြီ — Gemini Canvas "Pali Translate AI" app ထဲ upload → အပေါ်က "%sပြန်" ခလုပ်ကို ရွေးပြီး ▶ (ရလဒ် *_for%s_%s.txt ကို Downloads ထဲ ချမည်၊ ဤကိရိယာက ယူပါလိမ့်မည်)' % (len(files), LANG_NAME[L], L, L))
            if files: os.startfile(out)
            return
        out, files = t_core.build(n, 1, 10 ** 6, m, k, raw.get(), say, redo=redo.get())
        say('✔ ဖိုင် %d ခု ထွက်ပါပြီ — ဖိုင်ကို Gemini Canvas "Pali Translate AI" app ထဲ upload လုပ်ပြီး ခလုပ်တစ်ခါနှိပ်ပါ (ပြီးလျှင် ရလဒ်ကို Downloads ထဲ ချမည်၊ ဤကိရိယာက ယူပါလိမ့်မည်)' % len(files))
        if files: os.startfile(out)
    except BaseException as e: say('အမှား: %r' % e)
    finally: b1.config(state='normal')


def go1():
    try: m, k = max(1000, int(mc.get())), max(1, int(ns.get()))
    except ValueError: return messagebox.showerror('', 'ဂဏန်း ထည့်ပါ')
    n = sel(); b1.config(state='disabled'); say('ဖိုင်ထုတ်နေသည်...')
    threading.Thread(target=work1, args=(n, m, k), daemon=True).start()


def work_pub(n, auto=False, lang=''):
    try:
        if not auto and not messagebox.askyesno('web သို့ တင်မည်', 'စာအုပ် %03d ၏ %sပြန်ပြီးသည့် စာမျက်နှာများကို web (GitHub) သို့ တင်မည်လား?' % (n, LANG_NAME[lang or 'my'])): return
        say('web သို့ တင်နေသည်...'); t_core.publish(n, say, lang); m_status._TRK['t'] = 0; save_state(sheet=n, last_pub=n)
        if lang: return say('✔ %sပြန်ကို web သို့ တင်ပြီး — ပင်မစာမျက်နှာ၏ "%s" ခလုပ်ထဲ ပေါ်ပါလိမ့်မည်' % (LANG_NAME[lang], {'vi': 'Tiếng Việt', 'en': 'English'}[lang]))
        say('📌 နောက်ဆုံး web တင်ပြီးသော စာအုပ်: %03d (စာရင်းထဲ ဆက်ထားသည်)' % n)
    except BaseException as e: say('အမှား: %r' % e)
    finally: root.after(0, lambda: bpub.config(state='normal'))


def go_pub():
    n = sel(); bpub.config(state='disabled')
    threading.Thread(target=work_pub, args=(n, False, lang_var.get() if lang_var.get() in ('vi', 'en') else ''), daemon=True).start()


def after_ingest(n):       # a whole book is translated (no input file waiting any more) -> published by itself when the box is ticked
    # (called for the Burmese translation only: Vietnamese / English results stop in ingest_downloads)
    if autopub.get() and t_core.is_complete(n):
        say('✔ စာအုပ် %03d မြန်မာပြန် ပြည့်စုံပြီ — အလိုအလျောက် web သို့ တင်မည်' % n)
        threading.Thread(target=work_pub, args=(n, True), daemon=True).start()


def after_ingest_lang(n, lang):       # Vietnamese / English of a sheet finished (no input file waiting) -> published by itself when the box is ticked
    if autopub.get() and not glob.glob(os.path.join(t_core.OUT, 'tr_%03d_*_for%s.txt' % (n, lang))):
        say('✔ စာအုပ် %03d %sပြန် ပြည့်စုံပြီ — အလိုအလျောက် web သို့ တင်မည်' % (n, LANG_NAME[lang]))
        threading.Thread(target=work_pub, args=(n, True, lang), daemon=True).start()


def work_extra(n, pages):
    try:
        out, files = t_core.build(n, 1, 10 ** 6, 10000, 10, False, say, only=set(), extra_pali=set(pages), rest=True)
        if files: say('✔ ဖိုင် ထွက်ပါပြီ (နိဿယမပါ - ပါဠိမှ တိုက်ရိုက်ပြန်) — Gemini ထဲ တင်ပါ'); os.startfile(out)
    except BaseException as e: say('အမှား: %r' % e)
    finally: root.after(0, lambda: bextra.config(state='normal'))


def go_extra():
    import re as _re
    try: pages = [int(x) for x in _re.findall(r'\d+', extra_e.get())]
    except ValueError: pages = []
    if not pages: return messagebox.showerror('', 'ပါဠိစာမျက်နှာနံပါတ် ထည့်ပါ (ဥပမာ 213)')
    n = sel(); bextra.config(state='disabled'); say('နိဿယမပါသော ပါဠိမျက်နှာ ဖိုင်ထုတ်နေသည်...')
    threading.Thread(target=work_extra, args=(n, pages), daemon=True).start()


def export():
    n = sel(); L = lang_var.get()
    if L in ('vi', 'en'):
        d = t_core.load_translations(n, L); p = os.path.join(t_core.GOLD, 'tr_%03d_%s.txt' % (n, L))
        open(p, 'w', encoding='utf-8').write((chr(10) * 2).join('--- ပါဠိစာမျက်နှာ %d ---' % k + chr(10) + d[k] for k in sorted(d))); say('✔ %sပြန် ပါဠိ %d မျက်နှာ -> %s' % (LANG_NAME[L], len(d), p)); return os.startfile(p)
    p, c = t_core.export_book(n); say('✔ မြန်မာပြန် ပါဠိ %d မျက်နှာ -> %s' % (c, p)); os.startfile(p)


def count():
    n = sel(); L = lang_var.get()
    if L in ('vi', 'en'):
        tot, got = t_core.lang_progress(n, L); return say('စာအုပ် %03d: မြန်မာပြန်ပြီး ပါဠိ %d မျက်နှာအနက် %sပြန်ပြီး %d မျက်နှာ' % (n, tot, LANG_NAME[L], got))
    d = t_core.load_translations(n); say('စာအုပ် %03d: မြန်မာပြန်ပြီး ပါဠိ %d မျက်နှာ%s' % (n, len(d), (' (%d–%d)' % (min(d), max(d))) if d else ''))


b1 = ttk.Button(bf, text='① Gemini ဖိုင် ထုတ်မည်', command=go1); b1.pack(side='left', padx=3)
ttk.Button(bf, text='output folder', command=lambda: (os.makedirs(t_core.OUT, exist_ok=True), os.startfile(t_core.OUT))).pack(side='left', padx=3)
ttk.Button(bf, text='② မြန်မာပြန်ပြီး စာမျက်နှာ အရေအတွက်', command=count).pack(side='left', padx=3)
ttk.Button(bf, text='③ မြန်မာပြန် စာအုပ် ထုတ် (.txt)', command=export).pack(side='left', padx=3)
bpub = tk.Button(bf, text='▲  web သို့ တင်', bg='#2a7a3b', fg='white', activebackground='#1f5c2b', activeforeground='white', font=('', 10, 'bold'), padx=10, command=go_pub); bpub.pack(side='left', padx=6)
autopub = tk.BooleanVar(value=True)
ex = ttk.Frame(f); ex.grid(row=7, column=0, columnspan=2, sticky='w')
ttk.Label(ex, text='နိဿယမတွဲရသော ပါဠိမျက်နှာ (မြေပုံထဲ မပါ - ပါဠိမှ တိုက်ရိုက်ပြန်) ဥပမာ 213 :').pack(side='left'); extra_e = ttk.Entry(ex, width=12); extra_e.pack(side='left', padx=3)
bextra = ttk.Button(ex, text='④ ဤမျက်နှာများ ဖိုင်ထုတ်', command=go_extra); bextra.pack(side='left', padx=3)
ttk.Checkbutton(bf, text='စာအုပ်တစ်အုပ်လုံး ပြီးလျှင် အလိုအလျောက် တင်', variable=autopub).pack(side='left', padx=3)
ttk.Label(f, text='လုပ်ပုံ: ① → ဖိုင်ကို Gemini "Pali Translate AI" app ထဲ upload → ▶ → *_translated.txt Downloads ထဲ ရောက်လျှင် ၅ စက္ကန့်တစ်ခါ အလိုလို ယူ → ③', foreground='#555').grid(row=4, column=0, columnspan=2, sticky='w')


def poll():
    try:
        if t_core.ingest_downloads(say, after_ingest, after_ingest_lang): pass
    except Exception as e: say('ingest အမှား: %r' % e)
    try: refresh_books()
    except Exception as e: say('စာရင်း အမှား: %r' % e)
    root.after(5000, poll)
def _resume_start():
    try: t_core.resume_partial(say)
    except Exception as e: say('resume အမှား: %r' % e)
    try: t_core.ensure_missing_lang(say)
    except Exception as e: say('resume (vi/en) အမှား: %r' % e)
root.after(1500, _resume_start)          # half-translated input files get their _rest file when the tool starts
root.after(2000, poll)
root.mainloop()

# -*- coding: utf-8 -*-
"""Button tool.  ① read the new xlsx  ② viewer  ③ files for Gemini  ④ paste Gemini's answer (collects + checks)  ⑤ final xlsx for Google Sheets"""
import os, sys, glob, threading, subprocess, tkinter as tk
from tkinter import ttk, messagebox, filedialog
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); TIPI = os.path.dirname(ROOT)
sys.path.insert(0, HERE)
# every helper program (git, python ...) started from here runs WITHOUT a console window (otherwise a black window flashes open and shut again and again while publishing)
class _NoWinPopen(subprocess.Popen):
    def __init__(self, *a, **k):
        if os.name == 'nt': k.setdefault('creationflags', 0x08000000)
        super().__init__(*a, **k)
subprocess.Popen = _NoWinPopen
import m_tool, m_bundle, m_gcheck

root = tk.Tk(); root.title('နိဿယ ပြင်ဆင်ကိရိယာ'); root.geometry('1000x860')
import json as _jj
def _published():       # sheets whose web file is already in the tipitaka repository (data/<file>.html)
    out = set()
    for mp in glob.glob(os.path.join(ROOT, 'web', '*.meta.json')):
        try:
            m = _jj.load(open(mp, encoding='utf-8'))
            if os.path.exists(os.path.join(TIPI, 'data', m['file'] + '.html')): out.add(int(m['sheet']))
        except Exception: pass
    return out
def _hide_on():
    try: return bool(_jj.load(open(os.path.join(ROOT, 'gui_state.json'), encoding='utf-8')).get('hide_pub', True))
    except Exception: return True
def visible_sheets(hide=None, keep=None):
    allb = m_tool.list_sheets()
    if hide is None: hide = _hide_on()
    if not hide: return allb
    pub = _published()
    return [(n, t) for n, t in allb if n not in pub or n == keep]
sheets = visible_sheets()
f = ttk.Frame(root, padding=10); f.pack(fill='both', expand=True); f.columnconfigure(1, weight=1); f.rowconfigure(9, weight=1)


def newest_xlsx():
    c = [p for p in glob.glob(os.path.join(TIPI, '*.xlsx')) if 'bold' not in os.path.basename(p)]
    return max(c, key=os.path.getmtime) if c else ''


ttk.Label(f, text='စာအုပ်', font=('', 11, 'bold')).grid(row=0, column=0, sticky='w')
STATE = os.path.join(ROOT, 'gui_state.json')
cb = ttk.Combobox(f, values=[t for n, t in sheets], state='readonly'); cb.grid(row=0, column=1, columnspan=4, sticky='we')
try:                                                                                    # the book chosen last time is chosen again; the first time NO book is chosen
    import json as _j
    _last = _j.load(open(STATE, encoding='utf-8')).get('sheet')
    for _i, (_n, _t) in enumerate(sheets):
        if _n == _last: cb.current(_i)
except Exception: pass
hidepub = tk.BooleanVar(value=_hide_on())
def _toggle_hide():
    keep = sheets[cb.current()][0] if cb.current() >= 0 else None
    try:
        st = _jj.load(open(STATE, encoding='utf-8'))
    except Exception: st = {}
    st['hide_pub'] = bool(hidepub.get())
    try: _jj.dump(st, open(STATE, 'w', encoding='utf-8'))
    except Exception: pass
    refresh_books(keep)
ttk.Checkbutton(f, text='web ပေါ်တင်ပြီးသော စာအုပ်များ ဖျောက်', variable=hidepub, command=_toggle_hide).grid(row=0, column=6, sticky='w', padx=4)
cur_lbl = tk.Label(f, text='', font=('', 12, 'bold'), anchor='w', width=36); cur_lbl.grid(row=0, column=5, sticky='w', padx=8)
def show_book(*_):
    import json as _j
    if cb.current() < 0: cur_lbl.config(text='⚠ စာအုပ် မရွေးရသေးပါ', fg='#b00020'); return
    _t = ' '.join(str(sheets[cb.current()][1]).split()); _t = (_t[:32] + '…') if len(_t) > 32 else _t       # one short line only (a long / multi-line sheet name used to take the whole right half of the window)
    cur_lbl.config(text='● ' + _t, fg='#1b5e20')
    root.after(300, lambda: threading.Thread(target=_auto_missing, args=(sheets[cb.current()][0],), daemon=True).start())     # the chosen book: pages nobody has sent to Gemini yet get their file by themselves
    try: _j.dump({'sheet': sheets[cb.current()][0], 'hide_pub': bool(hidepub.get())}, open(STATE, 'w', encoding='utf-8'))
    except Exception: pass
cb.bind('<<ComboboxSelected>>', show_book); show_book()
ttk.Label(f, text='Google Sheet မှ download လုပ်ထားသော .xlsx').grid(row=1, column=0, sticky='w')
xl = ttk.Entry(f); xl.grid(row=1, column=1, columnspan=3, sticky='we'); xl.insert(0, newest_xlsx())
ttk.Button(f, text='ရွေးမည်...', command=lambda: (lambda p: p and (xl.delete(0, 'end'), xl.insert(0, p)))(filedialog.askopenfilename(initialdir=TIPI, filetypes=[('Excel', '*.xlsx')]))).grid(row=1, column=4)

r = ttk.Frame(f); r.grid(row=2, column=0, columnspan=5, sticky='w', pady=6)
ttk.Label(r, text='ပါဠိစာမျက်နှာ').pack(side='left'); pl = ttk.Entry(r, width=5); pl.pack(side='left', padx=3); pl.insert(0, '7')
ttk.Label(r, text='မှ').pack(side='left'); ph = ttk.Entry(r, width=5); ph.pack(side='left', padx=3); ph.insert(0, '26')
ttk.Label(r, text='ထိ    အစုတစ်စုမှာ နိဿယစာမျက်နှာ ခန့်').pack(side='left'); per = ttk.Entry(r, width=3); per.pack(side='left', padx=3); per.insert(0, '7')
ttk.Label(r, text='(±၁)   ဖိုင်တစ်ခုမှာ အစု').pack(side='left'); nsets = ttk.Entry(r, width=3); nsets.pack(side='left', padx=3); nsets.insert(0, '10')
ttk.Label(r, text='   စာလုံးရေ အများဆုံး (အစုတစ်စု)').pack(side='left'); maxc = ttk.Entry(r, width=6); maxc.pack(side='left', padx=3); maxc.insert(0, '10000')
def maxchars_():
    try: return max(1000, int(maxc.get().replace(' ', '').replace(',', '')))
    except ValueError: return 10000
ttk.Label(r, text='စု').pack(side='left')
pali = tk.BooleanVar(value=True)
ttk.Checkbutton(f, text='ပါဠိစာလုံးပေါင်း ပြင်ချက် (အပြာ) ပါအောင်', variable=pali).grid(row=3, column=0, columnspan=5, sticky='w')

fr = ttk.Frame(f); fr.grid(row=6, column=0, columnspan=5, sticky='w', pady=4)
ttk.Label(fr, text='viewer ပြင်ချက် တွက်မည့် နိဿယစာမျက်နှာ').pack(side='left'); fl = ttk.Entry(fr, width=5); fl.pack(side='left', padx=3); fl.insert(0, '1')
ttk.Label(fr, text='မှ').pack(side='left'); fh = ttk.Entry(fr, width=5); fh.pack(side='left', padx=3); fh.insert(0, '40')
ttk.Label(fr, text='ထိ   ').pack(side='left')
whole = tk.BooleanVar(value=True)
ttk.Checkbutton(fr, text='တစ်အုပ်လုံး (၁၀ မိနစ်ခန့်)', variable=whole).pack(side='left')

bf = ttk.Frame(f); bf.grid(row=4, column=0, columnspan=5, sticky='we', pady=6)
def group(title):
    g = ttk.LabelFrame(bf, text=title, padding=(6, 3)); g.pack(fill='x', pady=2); return g
g1 = group('၁။ စာအုပ်ကို ပြင်ဆင်ရန်  (Google Sheet ကနေ xlsx ဆွဲပြီးနောက်)')
b1 = ttk.Button(g1, text='① ဖိုင်အသစ် ဖတ်မည်'); b1.pack(side='left', padx=3)
b7 = ttk.Button(g1, text='viewer ပြင်ဆင် (အပြာ + အမှိုက်ရှင်း)'); b7.pack(side='left', padx=3)
b2 = ttk.Button(g1, text='② viewer ဖွင့်မည်'); b2.pack(side='left', padx=3)
b13 = ttk.Button(g1, text='Gemini ဖိုင် ထုတ် (အမှိုက်ရှင်းပြီးမှ)'); b13.pack(side='left', padx=3)
g2 = group('၂။ Gemini ဖြင့် စစ်ရန်')
b3 = ttk.Button(g2, text='③ Gemini ဖိုင်ထုတ် (စာမျက်နှာအကွာအဝေး)'); b3.pack(side='left', padx=3)
b4 = ttk.Button(g2, text='④ Gemini ရလဒ် ထည့်/ပြင် (clipboard)'); b4.pack(side='left', padx=3)
b5 = ttk.Button(g2, text='⑤ final.xlsx ထုတ်'); b5.pack(side='left', padx=3)
b6 = ttk.Button(g2, text='output folder'); b6.pack(side='left', padx=3)
g3 = group('၃။ Gemini ပြီးနောက် စစ်ရန်')
b11 = ttk.Button(g3, text='Gemini ပြီးနောက် ပါဠိပြန်စစ်'); b11.pack(side='left', padx=3)
b8 = ttk.Button(g3, text='web ဒေတာ ထုတ်'); b8.pack(side='left', padx=3)
b9 = ttk.Button(g3, text='web ကြိုကြည့်'); b9.pack(side='left', padx=3)
g4 = group('၄။ web ပေါ်သို့ တင်ရန်  (GitHub - ဆိုက်ပေါ် ပြောင်းမည်)')
b10 = tk.Button(g4, text='▲  web သို့ တင်  (GitHub)', bg='#2a7a3b', fg='white', activebackground='#1f5c2b', activeforeground='white', font=('', 11, 'bold'), padx=14, pady=4); b10.pack(side='left', padx=3)
autopub = tk.BooleanVar(value=True)
ttk.Checkbutton(g4, text='စာအုပ်တစ်အုပ်လုံး ပြီးလျှင် အလိုအလျောက် တင်', variable=autopub).pack(side='left', padx=3)
_pub_lock = threading.Lock()
ttk.Label(g4, text='စာအုပ်ကို အပေါ်မှ ရွေးပြီး နှိပ်ပါ - အတည်ပြုမေးပြီးမှ တင်သည်').pack(side='left', padx=8)
g5 = group('၅။ စာအုပ်အသစ်များ  (နိဿယပေါင်းစုံ.xlsx ထဲက စာအုပ်တွေ ကုန်သွားလျှင် - တခြား .xlsx ဖိုင်)')
b12 = ttk.Button(g5, text='➕ တခြား xlsx ဖိုင်ထဲက စာအုပ်အသစ်များ ထည့်'); b12.pack(side='left', padx=3)
ttk.Label(g5, text='ရှိပြီးသား စာအုပ်ကို မထိ၊ sheet အသစ်ကိုပဲ ယူပြီး စာအုပ်စာရင်းထဲ ထည့်သည်').pack(side='left', padx=8)
g6 = group('၆။ စာသားမရှိ/တိုလွန်းသော စာမျက်နှာများ  (PDF → ပုံ → Google Drive/Sheet OCR → ပြန်ဖတ် → Gemini)')
b14 = ttk.Button(g6, text='🔍 ရှာ + PDF မှ ပုံထုတ်'); b14.pack(side='left', padx=3)
b16 = ttk.Button(g6, text='📁 ပုံ folder'); b16.pack(side='left', padx=3)
b15 = ttk.Button(g6, text='✔ OCR စာပြန်ရပြီ → Gemini ပြန်စစ်ရန် ပြင်'); b15.pack(side='left', padx=3)
g6b = ttk.Frame(g6); g6b.pack(fill='x', pady=2)
ttk.Label(g6b, text='PDF စာမျက်နှာ ၁ (အလိုအလျောက်ဆို အလွတ်)').pack(side='left'); ocf = ttk.Entry(g6b, width=5); ocf.pack(side='left', padx=3)
ttk.Label(g6b, text='   စာလုံးရေ ဤထက်နည်းလျှင် တိုလွန်း').pack(side='left'); ocs = ttk.Entry(g6b, width=5); ocs.pack(side='left', padx=3); ocs.insert(0, '150')
ttk.Label(g6b, text='   လက်ဖြင့်ထပ်ထည့်မည့် စာမျက်နှာ (ဥပမာ 17, 30-33)').pack(side='left'); oce = ttk.Entry(g6b, width=18); oce.pack(side='left', padx=3)
ttk.Label(f, text='လုပ်ပုံ: ① → viewer ပြင်ဆင် → viewer မှာ အမှိုက်ရှင်း (🗑 ပြီး 🔄) → Gemini ဖိုင် ထုတ် → ③ (ဖိုင်တစ်ခုချင်းကို Gemini ထဲ ကူးထည့်) → ရလဒ်ကို copy ပြီး ④ (ဖိုင်တိုင်းအတွက် ထပ်ခါထပ်ခါ) → ⑤ → Google Sheet ထဲ ကော်လံ C ကူးထည့်', foreground='#555').grid(row=5, column=0, columnspan=5, sticky='w')
log = tk.Text(f, height=16); log.grid(row=9, column=0, columnspan=5, sticky='nsew')


def say(s): root.after(0, lambda: (log.insert('end', str(s) + '\n'), log.see('end')))
def busy(on): root.after(0, lambda: [b.config(state='disabled' if on else 'normal') for b in (b1, b3, b7, b13)])
def sel():
    if cb.current() < 0:
        messagebox.showerror('စာအုပ် မရွေးရသေးပါ', 'အပေါ်ဆုံးက "စာအုပ်" ကွက်မှာ စာအုပ်ကို အရင်ရွေးပါ။')
        raise RuntimeError('no book chosen')
    return sheets[cb.current()][0]


def run(cmd):
    p = subprocess.Popen(cmd, cwd=TIPI, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    for line in p.stdout:
        if len(line) < 300: say(line.rstrip())
    return p.wait()


def set_fix_range():
    import json
    fp = os.path.join(ROOT, 'fix_on.json')
    d = json.load(open(fp, encoding='utf-8')) if os.path.exists(fp) else {}
    d[str(sel())] = [1, 9999] if whole.get() else [int(fl.get()), int(fh.get())]
    json.dump(d, open(fp, 'w', encoding='utf-8'))
    return d[str(sel())]


def work7():
    try:
        import m_prepare
        m_prepare.prepare_viewer(sel(), say)
    except Exception as e: say("အမှား: %s" % e)
    finally: busy(False)


def work13():
    try:
        import m_prepare
        m_prepare.prepare_files(sel(), 2, max(1, int(nsets.get())), not pali.get(), say, nsy=max(1, int(per.get())), maxchars=maxchars_())
    except Exception as e: say("အမှား: %s" % e)
    finally: busy(False)


def work1():
    try:
        p = xl.get().strip()
        if not os.path.exists(p): return say('ဖိုင်မတွေ့ပါ: ' + p)
        say('ဖိုင်ဖတ်နေသည် (၂-၅ မိနစ်ကြာနိုင်သည်)...')
        if run([sys.executable, os.path.join(HERE, 'm_extract.py'), p, 'auto']): return say('အမှား — ဖိုင်ဖတ်မရပါ')
        say('ရွေးထားသော စာအုပ်ကို viewer အတွက် ပြန်စီနေသည် (ကုဒ်ပြင်ချက်: ' + str(set_fix_range()) + ')...')
        run([sys.executable, os.path.join(HERE, 'm_pair.py'), str(sel())])
        say('✔ အဆင့် ① ပြီးပါပြီ။')
    except Exception as e: say('အမှား: %r' % e)
    finally: busy(False)


def work3(n, a, b, k, m):
    try:
        out, files = m_bundle.main(n, a, b, 2, False, not pali.get(), say, sets=m, nsy=k, maxchars=maxchars_())
        say('✔ ဖိုင် %d ခု ထွက်ပါပြီ — ဖိုင်ကို Gemini Canvas app ထဲ upload လုပ်ပြီး ခလုပ်တစ်ခါနှိပ်ပါ (အားလုံးစစ်ပြီးလျှင် ရလဒ်ကို Downloads ထဲ အလိုအလျောက်ချပြီး ဒီကိရိယာက ယူပါလိမ့်မည်)' % len(files)); os.startfile(out)
    except BaseException as e: say('အမှား: %r' % e)
    finally: busy(False)


def go3():
    try: a, b, k, m = int(pl.get()), int(ph.get()), max(1, int(per.get())), max(1, int(nsets.get()))
    except ValueError: return messagebox.showerror('', 'ဂဏန်း ထည့်ပါ')
    busy(True); say('ဖိုင်ထုတ်နေသည်... (ပါဠိ ၂၀ မျက်နှာလျှင် ၁-၂ မိနစ်ခန့်)')
    threading.Thread(target=work3, args=(sel(), a, b, k, m), daemon=True).start()


def go4():
    """the Myanmar text is edited in Notepad (the Tk text box moves/changes Myanmar letters): the text goes to a file, Notepad opens it, then 'save' collects the file"""
    import json
    ef = os.path.join(ROOT, 'gold', 'gemini', '_edit.txt'); os.makedirs(os.path.dirname(ef), exist_ok=True)
    nl = chr(10)
    top = tk.Toplevel(root); top.title('Gemini ရလဒ်'); top.geometry('560x230')
    msg = ttk.Label(top, text='', wraplength=520, justify='left'); msg.pack(padx=12, pady=10, anchor='w')
    def open_notepad(text, what):
        open(ef, 'w', encoding='utf-8').write(text)
        subprocess.Popen(['notepad.exe', ef], creationflags=0)
        msg.config(text=what + nl + 'Notepad ထဲမှာ ပြင်ပါ → Ctrl+S နှိပ်ပြီး သိမ်းပါ → ဒီပြတင်းပေါက်က "✔ Notepad ထဲက စာကို သိမ်းမည်" ကိုနှိပ်ပါ။' + nl + '(--- နိဿယ စာမျက်နှာ N --- စာကြောင်းများကို မဖျက်ပါနှင့်)')
    def from_clip():
        try: txt = root.clipboard_get()
        except tk.TclError: return messagebox.showerror('', 'clipboard ထဲ စာမရှိပါ — Gemini ရလဒ်ကို copy အရင်လုပ်ပါ', parent=top)
        open_notepad(txt, 'clipboard ထဲက Gemini စာကို Notepad ထဲ ဖွင့်ထားသည်။')
    def from_collected():
        cp = os.path.join(ROOT, 'gold', 'gemini', '%03d_collected.json' % sel())
        if not os.path.exists(cp): return messagebox.showinfo('', 'စုထားသော စာမျက်နှာ မရှိသေးပါ', parent=top)
        C = json.load(open(cp, encoding='utf-8'))
        open_notepad((nl * 2).join('--- နိဿယ စာမျက်နှာ %s ---%s%s' % (k, nl, C[k]) for k in sorted(C, key=int)), 'စုထားပြီးသား စာမျက်နှာများကို Notepad ထဲ ဖွင့်ထားသည်။')
    def save():
        if not os.path.exists(ef): return messagebox.showinfo('', 'အရင် စာကို Notepad ထဲ ဖွင့်ပါ', parent=top)
        text = open(ef, encoding='utf-8-sig').read()
        try: n_ = sel(); pv = m_gcheck.preview(n_, text)
        except RuntimeError: return
        except BaseException as e: return messagebox.showerror('', 'စာကို မဖတ်နိုင်ပါ: %r' % e, parent=top)
        if not pv['pages']: return messagebox.showerror('', "'--- နိဿယ စာမျက်နှာ N ---' စာကြောင်း မတွေ့ပါ", parent=top)
        nl = chr(10); pg = pv['pages']
        msg = 'ဤစာကို ဤစာအုပ်ထဲ ထည့်မည်:' + nl + '   ' + cb.get() + nl * 2 + 'စာမျက်နှာ %d မှ %d (%d မျက်နှာ)' % (pg[0], pg[-1], len(pg))
        if pv['replace']: msg += nl + '⚠ အရင်ထည့်ပြီးသား %d မျက်နှာကို အစားထိုးမည် (%d မှ %d)' % (len(pv['replace']), pv['replace'][0], pv['replace'][-1])
        if pv['other']: msg += nl * 2 + '⛔ သတိ: ဤစာသည် ဤစာအုပ်နှင့် မကိုက်ပါ၊ စာအုပ် %d နှင့် ပိုကိုက်သည်။ စာအုပ်မှား နေနိုင်သည်!' % pv['other'][0]
        elif pv['bad']: msg += nl * 2 + '⚠ စာမျက်နှာ %d ခုက ဤစာအုပ်နှင့် မကိုက်သယောင် (ကိုက်ညီမှု နည်း)' % len(pv['bad'])
        msg += nl * 2 + 'ထည့်မလား?'
        if not messagebox.askyesno('ထည့်ရန် အတည်ပြုပါ', msg, icon='warning' if (pv['other'] or pv['bad'] or pv['replace']) else 'question', default='no' if pv['other'] else 'yes', parent=top): return
        def w():
            try: m_gcheck.run(sel(), text, log=say)
            except BaseException as e: say('အမှား: %r' % e)
        threading.Thread(target=w, daemon=True).start(); top.destroy()
    bar = ttk.Frame(top, padding=6); bar.pack(fill='x')
    ttk.Button(bar, text='clipboard စာကို Notepad ဖွင့်', command=from_clip).pack(side='left', padx=3)
    ttk.Button(bar, text='စုထားသော စာများကို Notepad ဖွင့်', command=from_collected).pack(side='left', padx=3)
    bar2 = ttk.Frame(top, padding=6); bar2.pack(fill='x')
    ttk.Button(bar2, text='✔ Notepad ထဲက စာကို သိမ်းမည်', command=save).pack(side='left', padx=3)
    ttk.Button(bar2, text='မသိမ်းဘဲ ပိတ်', command=top.destroy).pack(side='left', padx=3)
    from_clip()


def go5():
    def w():
        try: p = m_gcheck.final(None, say); os.startfile(os.path.dirname(p))
        except BaseException as e: say('အမှား: %r' % e)
    threading.Thread(target=w, daemon=True).start()


b1.config(command=lambda: (busy(True), threading.Thread(target=work1, daemon=True).start()))
b2.config(command=lambda: (subprocess.Popen(['cmd', '/c', 'start', '', os.path.join(ROOT, 'run_viewer.bat')], cwd=ROOT, creationflags=0), say('viewer ဖွင့်နေသည် (browser ပွင့်လာမည်)')))
def work8():
    try:
        say('web ဒေတာ ထုတ်နေသည် (စာပိုဒ်ခွဲ၊ ပါဠိစာလုံးမည်း၊ 🔖) — ၁-၂ မိနစ်ခန့်...')
        run([sys.executable, os.path.join(HERE, 'm_final.py'), str(sel())])
        say('✔ ပြီးပါပြီ — nissaya_multi/web/ ထဲမှာ ရှိသည်')
    except Exception as e: say('အမှား: %r' % e)
def go9():
    import socket, webbrowser, time
    s_ = socket.socket(); s_.settimeout(0.5)
    up = s_.connect_ex(('127.0.0.1', 8794)) == 0; s_.close()
    if not up:
        subprocess.Popen([sys.executable, os.path.join(HERE, 'm_server.py'), '8794'], cwd=TIPI, creationflags=0x08000000)
        time.sleep(2)
    webbrowser.open('http://127.0.0.1:8794/nissaya_multi/web_preview.html'); say('web ကြိုကြည့်ကို browser မှာ ဖွင့်နေသည်')
b9.config(command=go9)
def work10(n):
    try:
        import m_publish
        m_publish.publish(n, True, False, say)
    except BaseException as e: say('အမှား: %s' % e)
    finally: root.after(0, lambda: b10.config(state='normal'))
def go10():
    name = cb.get(); nl = chr(10)
    msg = 'ရွေးထားသော စာအုပ်:' + nl + name + nl * 2 + 'web ဖိုင် ပြန်ထုတ်ပြီး GitHub (sayadawtejinda/tipitaka) သို့ တင်မည်။' + nl + 'ဆိုက်ပေါ် ပြောင်းလဲမည် - တင်မလား?'
    if not messagebox.askyesno('web သို့ တင်မည်', msg): return
    b10.config(state='disabled'); say('web သို့ တင်နေသည်... (၂-၃ မိနစ်)')
    threading.Thread(target=work10, args=(sel(),), daemon=True).start()
def work11(n):
    try:
        import m_prepare
        m_prepare.recheck(n, say)
    except BaseException as e: say('အမှား: %s' % e)
    finally: root.after(0, lambda: b11.config(state='normal'))
def go11():
    b11.config(state='disabled'); threading.Thread(target=work11, args=(sel(),), daemon=True).start()
b11.config(command=go11)
b10.config(command=go10)


def refresh_books(keep=None):
    global sheets
    sheets = visible_sheets(bool(hidepub.get()), keep); cb['values'] = [t for n, t in sheets]
    cb.set('')
    for i, (n_, t_) in enumerate(sheets):
        if n_ == keep: cb.current(i)
    show_book()


def work12(path):
    try:
        import m_addbook
        keep = sheets[cb.current()][0] if cb.current() >= 0 else None
        new = m_addbook.add_book(path, say)
        root.after(0, lambda: refresh_books(keep))
        if new: say('✔ စာအုပ်စာရင်း ပြန်ယူပြီး - အပေါ်က "စာအုပ်" ကွက်မှာ စာအုပ်အသစ်ကို ရွေးပြီး ① မှ စပါ (ဖိုင်အသစ်ဖတ်စရာ မလိုတော့ - ဖတ်ပြီးသား၊ "viewer ပြင်ဆင်" ကို နှိပ်ပါ)')
    except BaseException as e: say('အမှား: %s' % e)
    finally: root.after(0, lambda: b12.config(state='normal'))


def go12():
    p = filedialog.askopenfilename(initialdir=TIPI, title='တခြား .xlsx ဖိုင်ကို ရွေးပါ', filetypes=[('Excel', '*.xlsx')])
    if not p: return
    if not messagebox.askyesno('အတည်ပြုပါ', 'ဤဖိုင်ထဲက sheet အသစ်များကို ထည့်မည်:' + chr(10) + p + chr(10) + chr(10) + 'ရှိပြီးသား စာအုပ်များကို မထိပါ။ ဖိုင်ကြီးလျှင် ၂-၅ မိနစ် ကြာနိုင်ပါသည်။', default='yes'): return
    b12.config(state='disabled'); say('စာအုပ်အသစ်များ ထည့်နေသည်: ' + p); threading.Thread(target=work12, args=(p,), daemon=True).start()
b12.config(command=go12)
def _oc_args():
    try: sh = int(ocs.get() or 150)
    except ValueError: sh = 150
    try: fi = int(ocf.get()) if ocf.get().strip() else None
    except ValueError: fi = None
    return sh, fi


def work14(n):
    try:
        import m_ocrfix
        sh, fi = _oc_args()
        out = m_ocrfix.images(n, oce.get(), fi, sh, say)
        if out: root.after(0, lambda: os.startfile(out)); say('နောက်တစ်ဆင့်: ဤ folder ကို Google Drive သို့ တင် → Google Sheet ဖြင့် စာပြောင်း → .xlsx ပြန် download → "① ဖိုင်အသစ် ဖတ်မည်" → "✔ OCR စာပြန်ရပြီ"')
    except BaseException as e: say('အမှား: %s' % e)
    finally: root.after(0, lambda: b14.config(state='normal'))


def work15(n):
    try:
        import m_ocrfix
        m_ocrfix.after_reread(n, _oc_args()[0], say)
    except BaseException as e: say('အမှား: %s' % e)
    finally: root.after(0, lambda: b15.config(state='normal'))


def go16():
    import glob as _g
    d = _g.glob(os.path.join(ROOT, 'output', 'ocr_images', '%03d_*' % sel()))
    os.startfile(d[0] if d else os.path.join(ROOT, 'output'))


b14.config(command=lambda: (b14.config(state='disabled'), threading.Thread(target=work14, args=(sel(),), daemon=True).start()))
b15.config(command=lambda: (b15.config(state='disabled'), threading.Thread(target=work15, args=(sel(),), daemon=True).start()))
b16.config(command=go16)
b8.config(command=lambda: threading.Thread(target=work8, daemon=True).start())
b7.config(command=lambda: (busy(True), threading.Thread(target=work7, daemon=True).start()))
b13.config(command=lambda: (busy(True), threading.Thread(target=work13, daemon=True).start()))
b3.config(command=go3); b4.config(command=go4); b5.config(command=go5)
b6.config(command=lambda: (os.makedirs(m_tool.OUT, exist_ok=True), os.startfile(m_tool.OUT)))
_miss_lock = threading.Lock()
def _on_web(n):          # the book's web file is COMMITTED in the tipitaka repository (a file only copied into data/ but not committed is not on the web)
    try:
        fp = glob.glob(os.path.join(ROOT, 'web', '*_sheet%03d.meta.json' % n)) + glob.glob(os.path.join(ROOT, 'web', '*_sheet%d.meta.json' % n))
        if not fp: return True          # unknown: do not make files by itself
        fn = _jj.load(open(fp[0], encoding='utf-8'))['file'] + '.html'
        return subprocess.run(['git', 'ls-files', '--error-unmatch', 'data/' + fn], cwd=TIPI, capture_output=True).returncode == 0
    except Exception: return False
def _auto_missing(n):
    """a book that is being worked on (not on the web yet): the pages that Gemini has not checked and that wait in no file are put into new files (…_gap.txt) - no button needed"""
    if not _miss_lock.acquire(blocking=False): return
    try:
        if _on_web(n): return
        if m_gcheck.make_missing(n, say): say('  ➜ စာအုပ် %03d: မစစ်ရသေးသော စာမျက်နှာများအတွက် ဖိုင်အသစ် ထုတ်ပြီးပါပြီ' % n)
    except BaseException as e: say('  ⚠ မစစ်ရသေးသော စာမျက်နှာ ဖိုင်ထုတ်ရာ အမှား: %r' % e)
    finally: _miss_lock.release()
def _auto_publish(n):
    import glob
    try:
        if m_gcheck.make_missing(n, say): return          # pages nobody has sent yet get their own file first (the book is not finished, nothing is published)
    except BaseException as e: say('  ⚠ မစစ်ရသေးသော စာမျက်နှာ ဖိုင်ထုတ်ရာ အမှား: %r' % e)
    left = glob.glob(os.path.join(ROOT, 'output', 'gemini', '%03d_*.txt' % n))
    if left: say('  (စာအုပ် %03d — Gemini ဖိုင် %d ခု ကျန်သေး၊ အားလုံးပြီးမှ web တင်မည်)' % (n, len(left))); return
    if not autopub.get(): say('  (စာအုပ် %03d အားလုံးပြီးပြီ - အလိုအလျောက် web တင်ခြင်း ပိတ်ထားသည်၊ ကိုယ်တိုင် တင်ပါ)' % n); return
    say('  ▲ စာအုပ် %03d ကို web သို့ အလိုအလျောက် တင်နေသည်...' % n)
    import m_publish
    with _pub_lock: m_publish.publish(n, True, False, say)
def _watch_downloads():
    """every 5 seconds: results that the Gemini Canvas app downloaded (…_checked.txt in Downloads) are put into their book by themselves"""
    import time
    while True:
        try: m_gcheck.ingest_downloads(say, _auto_publish)
        except BaseException as e: say('Downloads စောင့်ကြည့်မှု အမှား: %r' % e)
        time.sleep(5)
threading.Thread(target=_watch_downloads, daemon=True).start()
root.mainloop()

# -*- coding: utf-8 -*-
"""Pali -> Burmese translation tool (like run_tool): ① file for the Gemini 'Pali Translate AI' app  ② Gemini's answers are taken from Downloads  ③ translated book out."""
import os, sys, threading, tkinter as tk
from tkinter import ttk, messagebox
HERE = os.path.dirname(os.path.abspath(__file__)); NSY = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(NSY, 'scripts'))
import t_core, m_tool

root = tk.Tk(); root.title('ပါဠိ မြန်မာပြန် ကိရိယာ'); root.geometry('900x640')
f = ttk.Frame(root, padding=10); f.pack(fill='both', expand=True); f.columnconfigure(1, weight=1); f.rowconfigure(6, weight=1)
import glob, json
TIPI = os.path.dirname(NSY)
def published():        # only books whose checked web file is already in the tipitaka repository (same test as run_tool's "web ပေါ်တင်ပြီး")
    out = set()
    for mp in glob.glob(os.path.join(NSY, 'web', '*.meta.json')):
        try:
            m = json.load(open(mp, encoding='utf-8'))
            if os.path.exists(os.path.join(TIPI, 'data', m['file'] + '.html')): out.add(int(m['sheet']))
        except Exception: pass
    return out
def get_sheets():
    pub = published(); return [(n, t) for n, t in m_tool.list_sheets() if n in pub]
sheets = get_sheets()
ttk.Label(f, text='စာအုပ်', font=('', 11, 'bold')).grid(row=0, column=0, sticky='w')
cb = ttk.Combobox(f, values=[t for n, t in sheets], state='readonly'); cb.grid(row=0, column=1, sticky='we')
def refresh_books():        # a book that run_tool publishes later appears here by itself (checked every few seconds); the chosen book stays chosen
    global sheets
    new = get_sheets()
    if [n for n, t in new] == [n for n, t in sheets]: return
    keep = sheets[cb.current()][0] if cb.current() >= 0 else None
    sheets = new; cb['values'] = [t for n, t in sheets]
    for i, (n, t) in enumerate(sheets):
        if n == keep: cb.current(i)
    say('📚 စာအုပ်စာရင်း ပြောင်းသည် — web တင်ပြီးသော စာအုပ် %d အုပ်' % len(sheets))
r = ttk.Frame(f); r.grid(row=1, column=0, columnspan=2, sticky='w', pady=6)
ttk.Label(r, text='ပါဠိစာမျက်နှာ').pack(side='left'); pl = ttk.Entry(r, width=5); pl.pack(side='left', padx=3); pl.insert(0, '1')
ttk.Label(r, text='မှ').pack(side='left'); ph = ttk.Entry(r, width=5); ph.pack(side='left', padx=3); ph.insert(0, '20')
ttk.Label(r, text='ထိ    အစုတစ်စု စာလုံးရေ အများဆုံး').pack(side='left'); mc = ttk.Entry(r, width=6); mc.pack(side='left', padx=3); mc.insert(0, '10000')
ttk.Label(r, text='   ဖိုင်တစ်ခုမှာ အစု').pack(side='left'); ns = ttk.Entry(r, width=3); ns.pack(side='left', padx=3); ns.insert(0, '10')
raw = tk.BooleanVar(value=False)
ttk.Checkbutton(f, text='Gemini မစစ်ရသေးသော နိဿယစာမျက်နှာကို OCR စာဖြင့် ထည့် (မခြစ်လျှင် စစ်ပြီးသော နိဿယသာ ယူ၊ မစစ်ရသေးလျှင် ထိုပါဠိမျက်နှာကို ချန်)', variable=raw).grid(row=2, column=0, columnspan=2, sticky='w')
bf = ttk.Frame(f); bf.grid(row=3, column=0, columnspan=2, sticky='w', pady=6)
log = tk.Text(f, height=20); log.grid(row=6, column=0, columnspan=2, sticky='nsew')
def say(s): root.after(0, lambda: (log.insert('end', str(s) + chr(10)), log.see('end')))
def sel():
    if cb.current() < 0:
        messagebox.showerror('စာအုပ် မရွေးရသေးပါ', 'အပေါ်က "စာအုပ်" ကွက်မှာ အရင်ရွေးပါ။'); raise RuntimeError('no book')
    return sheets[cb.current()][0]


def work1(n, a, b, m, k):
    try:
        out, files = t_core.build(n, a, b, m, k, raw.get(), say)
        say('✔ ဖိုင် %d ခု ထွက်ပါပြီ — ဖိုင်ကို Gemini Canvas "Pali Translate AI" app ထဲ upload လုပ်ပြီး ခလုပ်တစ်ခါနှိပ်ပါ (ပြီးလျှင် ရလဒ်ကို Downloads ထဲ ချမည်၊ ဤကိရိယာက ယူပါလိမ့်မည်)' % len(files))
        if files: os.startfile(out)
    except BaseException as e: say('အမှား: %r' % e)
    finally: b1.config(state='normal')


def go1():
    try: a, b, m, k = int(pl.get()), int(ph.get()), max(1000, int(mc.get())), max(1, int(ns.get()))
    except ValueError: return messagebox.showerror('', 'ဂဏန်း ထည့်ပါ')
    n = sel(); b1.config(state='disabled'); say('ဖိုင်ထုတ်နေသည်...')
    threading.Thread(target=work1, args=(n, a, b, m, k), daemon=True).start()


def export():
    n = sel(); p, c = t_core.export_book(n); say('✔ မြန်မာပြန် ပါဠိ %d မျက်နှာ -> %s' % (c, p)); os.startfile(p)


def count():
    n = sel(); d = t_core.load_translations(n); say('စာအုပ် %03d: မြန်မာပြန်ပြီး ပါဠိ %d မျက်နှာ%s' % (n, len(d), (' (%d–%d)' % (min(d), max(d))) if d else ''))


b1 = ttk.Button(bf, text='① Gemini ဖိုင် ထုတ်မည်', command=go1); b1.pack(side='left', padx=3)
ttk.Button(bf, text='output folder', command=lambda: (os.makedirs(t_core.OUT, exist_ok=True), os.startfile(t_core.OUT))).pack(side='left', padx=3)
ttk.Button(bf, text='② မြန်မာပြန်ပြီး စာမျက်နှာ အရေအတွက်', command=count).pack(side='left', padx=3)
ttk.Button(bf, text='③ မြန်မာပြန် စာအုပ် ထုတ် (.txt)', command=export).pack(side='left', padx=3)
ttk.Label(f, text='လုပ်ပုံ: ① → ဖိုင်ကို Gemini "Pali Translate AI" app ထဲ upload → ▶ → *_translated.txt Downloads ထဲ ရောက်လျှင် ၅ စက္ကန့်တစ်ခါ အလိုလို ယူ → ③', foreground='#555').grid(row=4, column=0, columnspan=2, sticky='w')


def poll():
    try:
        if t_core.ingest_downloads(say): pass
    except Exception as e: say('ingest အမှား: %r' % e)
    try: refresh_books()
    except Exception as e: say('စာရင်း အမှား: %r' % e)
    root.after(5000, poll)
root.after(2000, poll)
root.mainloop()

# -*- coding: utf-8 -*-
"""Builds 'Pali Translate AI.txt' (Gemini Canvas app: Pali page -> Burmese translation) from the nissaya checker
('tipitaka/Pali Nissaya AI Checker v2.txt': same file upload / sets / auto-retry / auto-download code) + translate_prompt.txt.
    python make_canvas.py"""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'Pali Nissaya AI Checker v2.txt')
BS = chr(92)
s = open(SRC, encoding='utf-8').read()
prompt = open(os.path.join(HERE, 'translate_prompt.txt'), encoding='utf-8').read().strip().replace(BS, BS * 2).replace('`', "'").replace('${', '$ {')
a = s.index('const SYSTEM_PROMPT = `') + len('const SYSTEM_PROMPT = `'); b = s.index('`;', a)
s = s[:a] + prompt + s[b:]
rep = [
    ('ပါဠိနိဿယ AI စစ်ဆေးရေး အက်ပ် v2 (Pali Nissaya AI Checker)', 'ပါဠိ မြန်မာပြန် AI အက်ပ် (Pali Translate AI)'),
    ('ပါဠိနိဿယ AI စစ်ဆေးရေး အက်ပ် v2', 'ပါဠိ မြန်မာပြန် AI အက်ပ်'),
    ('ပါဠိနိဿယ AI စစ်ဆေးရေး အထောက်အကူပြု စနစ်', 'ပါဠိ မြန်မာပြန် AI အထောက်အကူပြု စနစ်'),
    ('စစ်ပြီး နိဿယများ', 'မြန်မာပြန်များ'),
    ('ပါဠိနှင့် နိဿယကို ထည့်ပြီး စစ်ဆေးပါ။', 'ပါဠိနှင့် နိဿယကို ထည့်ပြီး မြန်မာပြန်ပါ။'),
    ('အောက်ပါ စာသားတွင် ပါဠိတော်နှင့် နိဿယ ပါသည်။ ညွှန်ကြားချက်များအတိုင်း နိဿယစာမျက်နှာ တစ်ခုချင်းကို စစ်ပြင်၍ JSON ဖြင့် ပြန်ပေးပါ။',
     'အောက်ပါ စာသားတွင် ပါဠိစာမျက်နှာများနှင့် ၎င်းတို့၏ နိဿယ ပါသည်။ ညွှန်ကြားချက်များအတိုင်း ပါဠိစာမျက်နှာ တစ်ခုချင်းကို မြန်မာလို ဘာသာပြန်၍ JSON ဖြင့် ပြန်ပေးပါ။'),
    ('နိဿယ <b>${c.pages}</b> မျက်နှာ', 'ပါဠိ <b>${c.pages}</b> မျက်နှာ'),
    ('နိဿယ <b>${totP}</b> မျက်နှာ', 'ပါဠိ <b>${totP}</b> မျက်နှာ'),
    ('ပြင်ဆင်ခဲ့သော နေရာများ -', 'အဓိက ဝေါဟာရ ရွေးချယ်ချက် -'),
    ('စာလုံးပေါင်းများ စစ်ဆေးနေပါသည်', 'မြန်မာပြန်နေပါသည်'),
    ('စစ်ဆေးပြီးပါပြီ', 'ပြန်ပြီးပါပြီ'),
    ('စစ်ဆေးမှု ပြုလုပ်ရာတွင်', 'ဘာသာပြန်ရာတွင်'),
    ('corrections_made', 'key_terms'),
    ('full_nissaya_text', 'translation'),
    ("(inputFileName || 'nissaya_result')", "(inputFileName || 'translate_result')"),
    # NOT *_checked.txt: m_gcheck.ingest_downloads would take such a file for a nissaya check
    ("const name = base + '_checked.txt';", "const name = base + '_translated.txt';"),
    ('--- နိဿယ စာမျက်နှာ ${p.page_number} ---', '--- စာမျက်နှာ ${p.page_number} ---'),
    ('"--- နိဿယ စာမျက်နှာ N ---" ခြားပြီး', '"--- စာမျက်နှာ N ---" ခြားပြီး'),
    ('(?:နိဿယ)?' + BS + 's*စာမျက်နှာ', '(?:)' + BS + 's*စာမျက်နှာ'),      # ONLY "--- စာမျက်နှာ N ---" counts as an input page (the nissaya page markers are [နိဿယ မျက်နှာ K])
    ('အစု ${qi + 1}/${queue.length} စစ်မည်', 'အစု ${qi + 1}/${queue.length} ပြန်မည်'),
    ("l.innerText = 'စစ်မည်'", "l.innerText = 'မြန်မာပြန်မည်'"),
    ('<span id="checkLabel" class="truncate">စစ်မည်</span>', '<span id="checkLabel" class="truncate">မြန်မာပြန်မည်</span>'),
    ('else l.innerText = `အစု ${qi + 1}/${queue.length} ပြန်မည်`;', 'else l.innerText = `အစု ${qi + 1}/${queue.length} ပြန်မည်`;' + chr(10) + "            { const bt = document.getElementById('checkBtn'), fin = !!queue.length && qi >= queue.length; ['bg-emerald-700', 'hover:bg-emerald-800'].forEach(c => bt.classList.toggle(c, fin)); ['bg-amber-700', 'hover:bg-amber-800'].forEach(c => bt.classList.toggle(c, !fin)); }  // orange while sets are left, GREEN when all are done"),
]
for o, n in rep:
    if o not in s: print('NOT FOUND:', o[:60])
    s = s.replace(o, n)

# help text + placeholder: the input is per PALI page (### ပါဠိ / ### နိဿယ), the output is the Burmese translation
HELP = ('<p class="text-xs text-slate-500 mb-2 myanmar-text"><b>--- စာမျက်နှာ N ---</b> ဖြင့် ပါဠိစာမျက်နှာတစ်ခုချင်း ခြား၍ အောက်တွင် '
        '<b>### ပါဠိ</b> (ပြန်ရမည့်စာ) နှင့် <b>### နိဿယ</b> (အနက်ကိုးကား) ပါသည်။ <b>===== အစု N / M =====</b> ဖြင့် အစုများ ခြားထားလျှင် '
        'ခလုပ်ကို တစ်ခါနှိပ်လျှင် အစု တစ်စုစီ မြန်မာပြန်ပေးပြီး ရလဒ်များ ဆက်စုပေးပါမည်။</p>')
PH = ('placeholder="===== အစု 1 / 10 =====\n--- စာမျက်နှာ 7 ---\n### ပါဠိ\nဧဝံ ဝုတ္တေ, ဝေရဉ္ဇော ...\n### နိဿယ\n'
      'ဧဝံ၊ ဤသို့။ ဝုတ္တေ၊ ဟောအပ်သည်ရှိသော်။ ...\n--- စာမျက်နှာ 8 ---\n### ပါဠိ\n...\n### နိဿယ\n..."></textarea>')
s, n1 = re.subn(r'<p class="text-xs text-slate-500 mb-2 myanmar-text">\s*<b>===== ပါဠိ =====</b>.*?</p>', lambda m: HELP, s, count=1, flags=re.S)
s, n2 = re.subn(r'placeholder="===== ပါဠိ =====.*?"></textarea>', lambda m: PH, s, count=1, flags=re.S)
s, n3 = re.subn(r'<details class="mt-3">(\s*<summary[^>]*>ပါဠိကို သီးခြားအကွက်)', lambda m: '<details class="hidden">' + m.group(1), s)
print('help/placeholder/details', n1, n2, n3)
open(os.path.join(HERE, 'Pali Translate AI.txt'), 'w', encoding='utf-8', newline='\n').write(s)
print('ok', len(s))

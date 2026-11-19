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

# ---- three modes: မြန်မာပြန် (Pali -> Burmese, the main job) / ဗီယက်နမ် / အင်္ဂလိပ် (the Burmese translation file that came back is uploaded again and translated)
def _prompt(name): return open(os.path.join(HERE, name), encoding='utf-8').read().strip().replace(BS, BS * 2).replace('`', "'").replace('${', '$ {')
end = s.index('`;', s.index('const SYSTEM_PROMPT = `')) + 2
MODES_JS = (chr(10) + "        const PROMPT_VI = `" + _prompt('translate_prompt_vi.txt') + "`;" + chr(10) + "        const PROMPT_EN = `" + _prompt('translate_prompt_en.txt') + "`;" + chr(10)
    + "        let MODE = 'my';   // my = Pali -> Burmese, vi = Burmese -> Vietnamese, en = Burmese -> English" + chr(10)
    + "        const PROMPTS = { my: SYSTEM_PROMPT, vi: PROMPT_VI, en: PROMPT_EN };" + chr(10)
    + "        const SUFFIX = { my: '_translated.txt', vi: '_vi.txt', en: '_en.txt' };" + chr(10)
    + "        const MODE_LBL = { my: 'မြန်မာပြန်မည်', vi: 'ဗီယက်နမ်ပြန်မည်', en: 'အင်္ဂလိပ်ပြန်မည်' };" + chr(10)
    + "        const USER_PRE = { vi: 'အောက်ပါ စာသားတွင် ပါဠိစာမျက်နှာများနှင့် ၎င်းတို့၏ မြန်မာဘာသာပြန် ပါသည်။ ညွှန်ကြားချက်များအတိုင်း မြန်မာပြန်ကို (ပါဠိကို ကိုးကား၍) ဗီယက်နမ်ဘာသာသို့ စာမျက်နှာ တစ်ခုချင်း ပြန်၍ JSON ဖြင့် ပြန်ပေးပါ။', en: 'အောက်ပါ စာသားတွင် ပါဠိစာမျက်နှာများနှင့် ၎င်းတို့၏ မြန်မာဘာသာပြန် ပါသည်။ ညွှန်ကြားချက်များအတိုင်း မြန်မာပြန်ကို (ပါဠိကို ကိုးကား၍) အင်္ဂလိပ်ဘာသာသို့ စာမျက်နှာ တစ်ခုချင်း ပြန်၍ JSON ဖြင့် ပြန်ပေးပါ။' };" + chr(10)
    + "        function setMode(m) { MODE = m; ['my', 'vi', 'en'].forEach(k => { const b = document.getElementById('mode_' + k); if (!b) return; b.className = 'px-3 py-1.5 rounded-lg text-sm font-bold border ' + (k === m ? 'bg-amber-700 text-white border-amber-700' : 'bg-white text-amber-800 border-amber-400 hover:bg-amber-50'); }); try { updateLabel(); } catch (e) {} }" + chr(10) + "        setMode('my');" + chr(10))
s = s[:end] + MODES_JS + s[end:]
for o, n in [
    ("systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] }", "systemInstruction: { parts: [{ text: PROMPTS[MODE] }] }"),
    ("const name = base + '_translated.txt';", "const name = base + SUFFIX[MODE];"),
    ("l.innerText = 'မြန်မာပြန်မည်'", "l.innerText = MODE_LBL[MODE]"),
]:
    if o not in s: print('NOT FOUND:', o[:60])
    s = s.replace(o, n)
s, nu = re.subn(r"(userPrompt = `အောက်ပါ စာသားတွင် ပါဠိစာမျက်နှာများနှင့်[^" + chr(10) + r"]*\+ userPrompt;)", lambda m: m.group(1) + chr(10) + "            if (MODE !== 'my') userPrompt = USER_PRE[MODE] + String.fromCharCode(10, 10) + setText;", s, count=1)
print('userPrompt override', nu)
BAR = '<div id="modeBar" class="flex flex-wrap items-center gap-2 mb-3"><span class="text-xs text-slate-500 myanmar-text">ဘာသာပြန်မည့်ပုံစံ -</span><button id="mode_my" onclick="setMode(' + "'my'" + ')">မြန်မာပြန် (ပါဠိ → မြန်မာ)</button><button id="mode_vi" onclick="setMode(' + "'vi'" + ')">🇻🇳 ဗီယက်နမ်</button><button id="mode_en" onclick="setMode(' + "'en'" + ')">🇬🇧 အင်္ဂလိပ်</button><span class="text-xs text-slate-500 myanmar-text">(ဗီယက်နမ်/အင်္ဂလိပ်: ပြန်ရထားသော *_translated.txt ကို ထည့်)</span></div>'
a_ = '<div id="dropZone"'
assert s.count(a_) == 1
s = s.replace(a_, BAR + a_, 1)
s = s.replace('</script>', "        document.addEventListener('DOMContentLoaded', () => setMode('my'));" + chr(10) + "    </script>", 1) if False else s
s = s.replace("function updateLabel() {", "function updateLabel() {", 1)
open(os.path.join(HERE, 'Pali Translate AI.txt'), 'w', encoding='utf-8', newline='\n').write(s)
print('ok', len(s))

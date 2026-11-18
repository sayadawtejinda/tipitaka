# Pali -> မြန်မာပြန် (Gemini Canvas)

- `Pali Translate AI.txt` — Gemini Canvas တွင် ဖွင့်မည့် app (nissaya စစ် app v2 အခြေခံ၊ prompt ပြောင်း)။
- `translate_prompt.txt` — ညွှန်ကြားချက် (ဤဖိုင်ကိုပြင်၍ `python make_canvas.py` ပြန်run → app ပြန်ထွက်)။
- ရလဒ်ဖိုင်နာမည် `<ထည့်ဖိုင်>_translated.txt` (`_checked.txt` မဟုတ် — m_gcheck နှင့် မရောစေရန်)။

## ထည့်ဖိုင်ပုံစံ (ပါဠိစာမျက်နှာတစ်ခုချင်း၊ အစုတစ်စုလျှင် ၂–၃ မျက်နှာခန့်)
```
===== အစု 1 / 10 =====
--- စာမျက်နှာ 7 ---
### ပါဠိ
(ပါဠိစာ)
### နိဿယ
(ထိုပါဠိစာမျက်နှာနှင့် ကိုက်သော နိဿယ — မရှိလျှင် ဗလာ)
--- စာမျက်နှာ 8 ---
...
```
ရလဒ်: `--- စာမျက်နှာ N ---` + မြန်မာပြန်။ JSON field: `translation`, `key_terms`, `uncertain`။

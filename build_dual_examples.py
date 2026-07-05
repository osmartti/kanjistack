"""
Build dual example sentences per kanji: one using kunyomi context, one using onyomi context.
Also fills in missing English translations.

New ex structure:
  ex: { kun?: {s, f, t?}, on?: {s, f, t?} }

Uses heuristic (no pykakasi for filtering) then pykakasi only for furigana of chosen sentences.
Heuristic:
  - KUN context: kanji appears NOT flanked by other kanji (standalone / okurigana)
  - ON context:  kanji appears flanked by at least one other kanji (compound word)
"""
import sys, io, json, bz2, tarfile, re
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import pykakasi
except ImportError:
    print("pip install pykakasi"); sys.exit(1)

# ── Character helpers ─────────────────────────────────────────────────────
def is_kanji(c):
    return '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf'

def is_hiragana(c):
    return '\u3040' <= c <= '\u309f'

def kata_to_hira(t):
    return ''.join(chr(ord(c) - 0x60) if 0x30A0 <= ord(c) <= 0x30F6 else c for c in t)

def has_kanji(text):
    return any(is_kanji(c) for c in text)

# ── Reading helpers ───────────────────────────────────────────────────────
def get_kun_readings(k_entry):
    result = set()
    for r in k_entry.get('kun', []):
        r = r.lstrip('-')
        base = r.split('.')[0]
        if base: result.add(base)
    return result

def get_on_readings(k_entry):
    result = set()
    for r in k_entry.get('on', []):
        h = kata_to_hira(r.strip())
        if h: result.add(h)
    return result

# ── Sentence context heuristics (no pykakasi needed) ─────────────────────
def sentence_likely_kun(text, kanji_char):
    """Kanji appears NOT flanked by another kanji → likely kunyomi."""
    for i, c in enumerate(text):
        if c != kanji_char: continue
        before = text[i-1] if i > 0 else ''
        after  = text[i+1] if i < len(text)-1 else ''
        if not is_kanji(before) and not is_kanji(after): return True  # isolated
        if not is_kanji(before) and is_hiragana(after):  return True  # okurigana
    return False

def sentence_likely_on(text, kanji_char):
    """Kanji appears next to another kanji → likely onyomi compound."""
    for i, c in enumerate(text):
        if c != kanji_char: continue
        before = text[i-1] if i > 0 else ''
        after  = text[i+1] if i < len(text)-1 else ''
        if is_kanji(before) or is_kanji(after): return True
    return False

# ── pykakasi furigana ─────────────────────────────────────────────────────
def to_furigana(text, kks):
    parts = []
    for item in kks.convert(text):
        orig = item['orig']
        hira = item['hira']
        if not hira or hira == orig:
            parts.append([orig])
        else:
            parts.append([orig, hira])
    return parts

# ── Load data ─────────────────────────────────────────────────────────────
print('Loading kanji.json...', flush=True)
with open('public/kanji.json', encoding='utf-8') as f:
    kanji_data = json.load(f)

print('Loading Tatoeba sentences...', flush=True)
sentences = []
with bz2.open('jpn_sentences.tsv.bz2', 'rt', encoding='utf-8') as f:
    for line in f:
        parts = line.rstrip('\n').split('\t')
        if len(parts) >= 3:
            sid, text = int(parts[0]), parts[2]
            sentences.append((sid, text))
print(f'  {len(sentences):,} sentences', flush=True)

# Build text→id for translation lookup
jpn_text_to_id = {text: sid for sid, text in sentences}

print('Building sentence index...', flush=True)
all_kanji_chars = set(k['l'] for k in kanji_data)
kanji_sents = defaultdict(list)
for sid, text in sentences:
    for ch in set(text):
        if ch in all_kanji_chars:
            kanji_sents[ch].append((sid, text))
# Sort by length (prefer shorter, simpler sentences)
for ch in kanji_sents:
    kanji_sents[ch].sort(key=lambda x: len(x[1]))
print(f'  Index built', flush=True)

# ── Load translations ─────────────────────────────────────────────────────
print('Loading translation indices...', flush=True)
jpn_to_eng = {}
with tarfile.open('jpn_indices.tar.bz2', 'r:bz2') as tar:
    f = tar.extractfile('jpn_indices.csv')
    for line in f:
        parts = line.decode('utf-8').rstrip('\n').split('\t')
        if len(parts) >= 2:
            jpn_id, eng_id = int(parts[0]), int(parts[1])
            if jpn_id not in jpn_to_eng:
                jpn_to_eng[jpn_id] = eng_id

eng_texts = {}
with bz2.open('eng_sentences.tsv.bz2', 'rt', encoding='utf-8') as f:
    for line in f:
        parts = line.rstrip('\n').split('\t')
        if len(parts) >= 3:
            eng_texts[int(parts[0])] = parts[2]
print(f'  {len(jpn_to_eng):,} jpn→eng, {len(eng_texts):,} eng sentences', flush=True)

def get_translation(text):
    sid = jpn_text_to_id.get(text)
    if not sid: return None
    eid = jpn_to_eng.get(sid)
    if not eid: return None
    return eng_texts.get(eid)

# ── Init pykakasi ─────────────────────────────────────────────────────────
print('Initialising pykakasi...', flush=True)
kks = pykakasi.kakasi()
print('  ready', flush=True)

def pick_sentence(kanji_char, check_fn, candidates, max_candidates=80):
    """Find first candidate sentence matching check_fn; return (sid, text) or None."""
    checked = 0
    for sid, text in candidates:
        if not has_kanji(text): continue
        if 4 <= len(text) <= 25 and check_fn(text, kanji_char):
            return (sid, text)
        checked += 1
        if checked >= max_candidates: break
    # Fallback: any sentence containing the kanji with kanji chars
    for sid, text in candidates[:max_candidates]:
        if has_kanji(text) and 4 <= len(text) <= 25:
            return (sid, text)
    return None

def build_entry(sid, text):
    """Build {s, f, t?} entry for a sentence."""
    furigana = to_furigana(text, kks)
    entry = {'s': text, 'f': furigana}
    t = get_translation(text)
    if t:
        entry['t'] = {'en': t}
    return entry

# ── Process each kanji ────────────────────────────────────────────────────
print('\nProcessing kanji...', flush=True)
stats = {'kun_found': 0, 'on_found': 0, 'kun_miss': 0, 'on_miss': 0, 'skipped': 0}

for i, k in enumerate(kanji_data):
    kanji_char = k['l']
    candidates = kanji_sents.get(kanji_char, [])

    if not candidates:
        k.pop('ex', None)
        stats['skipped'] += 1
        continue

    has_kun = bool(get_kun_readings(k))
    has_on  = bool(get_on_readings(k))
    new_ex = {}

    if has_kun:
        result = pick_sentence(kanji_char, sentence_likely_kun, candidates)
        if result:
            new_ex['kun'] = build_entry(*result)
            stats['kun_found'] += 1
        else:
            stats['kun_miss'] += 1

    if has_on:
        # Try to find a DIFFERENT sentence than the kun one
        kun_text = new_ex.get('kun', {}).get('s', '')
        on_candidates = [(sid, t) for sid, t in candidates if t != kun_text]
        result = pick_sentence(kanji_char, sentence_likely_on, on_candidates)
        if result:
            new_ex['on'] = build_entry(*result)
            stats['on_found'] += 1
        else:
            stats['on_miss'] += 1

    if new_ex:
        k['ex'] = new_ex
    else:
        k.pop('ex', None)

    if (i+1) % 100 == 0:
        print(f'  {i+1}/{len(kanji_data)}  kun:{stats["kun_found"]}  on:{stats["on_found"]}', flush=True)

print(f'\nResults:', flush=True)
print(f'  Kun sentences found:   {stats["kun_found"]}', flush=True)
print(f'  On  sentences found:   {stats["on_found"]}', flush=True)
print(f'  Kun missing:           {stats["kun_miss"]}', flush=True)
print(f'  On  missing:           {stats["on_miss"]}', flush=True)
print(f'  No sentences at all:   {stats["skipped"]}', flush=True)

# ── Save ──────────────────────────────────────────────────────────────────
import os
with open('public/kanji.json', 'w', encoding='utf-8') as f:
    json.dump(kanji_data, f, ensure_ascii=False, separators=(',', ':'))
print(f'\nSaved kanji.json ({os.path.getsize("public/kanji.json")//1024} KB)', flush=True)

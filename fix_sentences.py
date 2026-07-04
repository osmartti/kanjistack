"""
Re-pick example sentences for kanji where the current sentence doesn't
actually use one of the kanji's own on/kun readings.
Uses pykakasi + jpn_sentences.tsv.bz2.
"""
import sys, io, json, bz2, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import pykakasi
except ImportError:
    print("pip install pykakasi"); sys.exit(1)

# ── Helpers ──────────────────────────────────────────────────────────────
def kata_to_hira(t):
    return ''.join(chr(ord(c) - 0x60) if 0x30A0 <= ord(c) <= 0x30F6 else c for c in t)

def base_readings(k_entry):
    """
    Return set of base readings (hiragana) for a kanji entry from kanji.json.
    For kun readings with dots (み.る), take only the part before the dot.
    For kun with leading dash (-び), strip the dash.
    """
    result = set()
    for r in k_entry.get('on', []):
        h = kata_to_hira(r.strip())
        if h: result.add(h)
    for r in k_entry.get('kun', []):
        r = r.lstrip('-')
        base = r.split('.')[0]   # take part before okurigana dot
        if base: result.add(base)
    return result

def sentence_uses_reading(kanji_char, known_readings, furigana_parts):
    """
    Return True if any word containing kanji_char has furigana that
    contains one of the known readings as a substring.
    """
    for part in furigana_parts:
        if len(part) == 2:
            word, reading = part
            if kanji_char in word:
                for kr in known_readings:
                    if kr and kr in reading:
                        return True
        elif len(part) == 1:
            # No furigana — the text itself is kana
            if kanji_char in part[0]:
                # Kanji appearing without furigana is unusual; skip
                pass
    return False

def to_furigana(text, kks):
    """Convert text to [[word, reading?], ...] furigana parts."""
    parts = []
    result = kks.convert(text)
    for item in result:
        orig = item['orig']
        hira = item['hira']
        if not hira or hira == orig:
            parts.append([orig])
        else:
            parts.append([orig, hira])
    return parts

def has_kanji(text):
    return any('\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf' for c in text)

# ── Load data ─────────────────────────────────────────────────────────────
print('Loading kanji.json...', flush=True)
with open('public/kanji.json', encoding='utf-8') as f:
    kanji_data = json.load(f)

# Build lookup
kanji_map = {k['l']: k for k in kanji_data}

# Find kanji with bad sentences (using corrected base reading logic)
print('Finding bad sentences...', flush=True)
bad_kanji = set()
for k in kanji_data:
    if not k.get('ex'):
        continue
    readings = base_readings(k)
    if not sentence_uses_reading(k['l'], readings, k['ex']['f']):
        bad_kanji.add(k['l'])

print(f'  {len(bad_kanji)} kanji need better sentences', flush=True)

# ── Load all Japanese sentences ───────────────────────────────────────────
print('Loading Tatoeba sentences...', flush=True)
sentences = []  # [(id, text)]
with bz2.open('jpn_sentences.tsv.bz2', 'rt', encoding='utf-8') as f:
    for line in f:
        parts = line.rstrip('\n').split('\t')
        if len(parts) >= 3:
            sid, _, text = int(parts[0]), parts[1], parts[2]
            sentences.append((sid, text))
print(f'  {len(sentences):,} sentences loaded', flush=True)

# Build index: kanji → list of (sid, text), sorted by length
print('Indexing sentences by kanji...', flush=True)
from collections import defaultdict
kanji_sents = defaultdict(list)
for sid, text in sentences:
    for ch in set(text):
        if ch in bad_kanji:
            kanji_sents[ch].append((sid, text))
# Sort by sentence length (prefer short sentences)
for ch in kanji_sents:
    kanji_sents[ch].sort(key=lambda x: len(x[1]))
print(f'  Index built', flush=True)

# Also build text→id map (for translation lookup later)
text_to_id = {text: sid for sid, text in sentences}

# ── Init pykakasi ─────────────────────────────────────────────────────────
print('Initialising pykakasi...', flush=True)
kks = pykakasi.kakasi()
print('  ready', flush=True)

# ── Find replacement sentences ────────────────────────────────────────────
print('Finding replacements...', flush=True)
replaced = 0
no_replacement = []

for k in kanji_data:
    kanji_char = k['l']
    if kanji_char not in bad_kanji:
        continue

    readings = base_readings(k)
    candidates = kanji_sents.get(kanji_char, [])
    found = False

    for sid, text in candidates:
        if not has_kanji(text):
            continue
        furigana = to_furigana(text, kks)
        if sentence_uses_reading(kanji_char, readings, furigana):
            # Keep old translation if available
            old_t = k['ex'].get('t') if k.get('ex') else None
            k['ex'] = {'s': text, 'f': furigana}
            if old_t:
                k['ex']['t'] = old_t
            found = True
            replaced += 1
            break

    if not found:
        no_replacement.append(kanji_char)

print(f'\nReplaced: {replaced}', flush=True)
print(f'No replacement found: {len(no_replacement)}  {" ".join(no_replacement[:30])}', flush=True)

# ── Save ──────────────────────────────────────────────────────────────────
import os
with open('public/kanji.json', 'w', encoding='utf-8') as f:
    json.dump(kanji_data, f, ensure_ascii=False, separators=(',', ':'))
print(f'\nkanji.json saved ({os.path.getsize("public/kanji.json")//1024} KB)', flush=True)

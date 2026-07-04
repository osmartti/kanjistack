"""
Add English translations to example sentences in kanji.json.
Uses jpn_indices.csv (jpn_id → eng_id) + eng_sentences.tsv.bz2.
No API calls needed — all offline.
"""
import sys, io, json, bz2, tarfile, urllib.request, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ENG_URL = ('https://downloads.tatoeba.org/exports/per_language/eng/'
           'eng_sentences.tsv.bz2')
ENG_FILE = 'eng_sentences.tsv.bz2'

# ── Download English sentences if not cached ──────────────────────────────
if not os.path.exists(ENG_FILE):
    print(f'Downloading {ENG_FILE} (~25 MB)...', flush=True)
    urllib.request.urlretrieve(ENG_URL, ENG_FILE)
    print(f'  done ({os.path.getsize(ENG_FILE)//1024} KB)', flush=True)
else:
    print(f'{ENG_FILE} already cached ({os.path.getsize(ENG_FILE)//1024} KB)',
          flush=True)

# ── Build jpn_id → eng_id from jpn_indices.csv ────────────────────────────
print('Loading jpn_indices...', flush=True)
jpn_to_eng = {}
with tarfile.open('jpn_indices.tar.bz2', 'r:bz2') as tar:
    f = tar.extractfile('jpn_indices.csv')
    for line in f:
        parts = line.decode('utf-8').rstrip('\n').split('\t')
        if len(parts) >= 2:
            jpn_id, eng_id = int(parts[0]), int(parts[1])
            if jpn_id not in jpn_to_eng:  # keep first mapping
                jpn_to_eng[jpn_id] = eng_id
print(f'  {len(jpn_to_eng):,} jpn→eng mappings', flush=True)

# ── Build eng_id → text ───────────────────────────────────────────────────
print('Loading English sentences...', flush=True)
eng_texts = {}
with bz2.open(ENG_FILE, 'rt', encoding='utf-8') as f:
    for line in f:
        parts = line.rstrip('\n').split('\t')
        if len(parts) >= 3:
            eng_texts[int(parts[0])] = parts[2]
print(f'  {len(eng_texts):,} English sentences', flush=True)

# ── Build jpn_text → jpn_id from jpn_sentences.tsv.bz2 ───────────────────
print('Building JPN text→id map...', flush=True)
jpn_text_to_id = {}
with bz2.open('jpn_sentences.tsv.bz2', 'rt', encoding='utf-8') as f:
    for line in f:
        parts = line.rstrip('\n').split('\t')
        if len(parts) >= 3:
            jpn_text_to_id[parts[2]] = int(parts[0])
print(f'  {len(jpn_text_to_id):,} JPN sentences indexed', flush=True)

# ── Apply to kanji.json ───────────────────────────────────────────────────
print('Applying translations...', flush=True)
with open('public/kanji.json', encoding='utf-8') as f:
    kanji_data = json.load(f)

added = no_jpn_id = no_eng_id = no_eng_text = 0
for k in kanji_data:
    if not k.get('ex'):
        continue
    jpn_id = jpn_text_to_id.get(k['ex']['s'])
    if not jpn_id:
        no_jpn_id += 1
        continue
    eng_id = jpn_to_eng.get(jpn_id)
    if not eng_id:
        no_eng_id += 1
        continue
    eng_text = eng_texts.get(eng_id)
    if not eng_text:
        no_eng_text += 1
        continue
    k['ex']['t'] = {'en': eng_text}
    added += 1

print(f'\nResults:', flush=True)
print(f'  English translations added:  {added}', flush=True)
print(f'  No JPN sentence ID found:    {no_jpn_id}', flush=True)
print(f'  No ENG mapping in indices:   {no_eng_id}', flush=True)
print(f'  ENG id not in sentences:     {no_eng_text}', flush=True)

# ── Save ──────────────────────────────────────────────────────────────────
with open('public/kanji.json', 'w', encoding='utf-8') as f:
    json.dump(kanji_data, f, ensure_ascii=False, separators=(',', ':'))
size = os.path.getsize('public/kanji.json') // 1024
print(f'\nkanji.json saved ({size} KB)', flush=True)

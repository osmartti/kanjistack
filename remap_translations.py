"""
Re-match English translations to current sentences in kanji.json.
Rebuilds ex.t from scratch using jpn_indices + eng_sentences.
"""
import sys, io, json, bz2, tarfile, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── Build text→id from jpn_sentences ──────────────────────────────────────
print('Building JPN text→id map...', flush=True)
jpn_text_to_id = {}
with bz2.open('jpn_sentences.tsv.bz2', 'rt', encoding='utf-8') as f:
    for line in f:
        p = line.rstrip('\n').split('\t')
        if len(p) >= 3:
            jpn_text_to_id[p[2]] = int(p[0])
print(f'  {len(jpn_text_to_id):,} JPN sentences', flush=True)

# ── Build jpn_id→eng_id from jpn_indices ──────────────────────────────────
print('Loading jpn_indices...', flush=True)
jpn_to_eng = {}
with tarfile.open('jpn_indices.tar.bz2', 'r:bz2') as tar:
    f = tar.extractfile('jpn_indices.csv')
    for line in f:
        p = line.decode('utf-8').rstrip('\n').split('\t')
        if len(p) >= 2:
            jid, eid = int(p[0]), int(p[1])
            if jid not in jpn_to_eng:
                jpn_to_eng[jid] = eid
print(f'  {len(jpn_to_eng):,} jpn→eng mappings', flush=True)

# ── Build eng_id→text ─────────────────────────────────────────────────────
print('Loading English sentences...', flush=True)
eng_texts = {}
with bz2.open('eng_sentences.tsv.bz2', 'rt', encoding='utf-8') as f:
    for line in f:
        p = line.rstrip('\n').split('\t')
        if len(p) >= 3:
            eng_texts[int(p[0])] = p[2]
print(f'  {len(eng_texts):,} English sentences', flush=True)

# ── Rebuild translations in kanji.json ────────────────────────────────────
print('Rebuilding translations...', flush=True)
with open('public/kanji.json', encoding='utf-8') as f:
    kanji_data = json.load(f)

added = replaced = removed = no_match = 0
for k in kanji_data:
    if not k.get('ex'):
        continue
    sentence = k['ex']['s']
    jpn_id = jpn_text_to_id.get(sentence)
    if not jpn_id:
        if 't' in k['ex']:
            del k['ex']['t']
            removed += 1
        no_match += 1
        continue
    eng_id = jpn_to_eng.get(jpn_id)
    eng_text = eng_texts.get(eng_id) if eng_id else None
    if eng_text:
        had = 't' in k['ex']
        k['ex']['t'] = {'en': eng_text}
        if had: replaced += 1
        else: added += 1
    else:
        if 't' in k['ex']:
            del k['ex']['t']
            removed += 1

print(f'  translations added:   {added}', flush=True)
print(f'  translations updated: {replaced}', flush=True)
print(f'  translations removed (no match): {removed}', flush=True)
print(f'  sentences with no JPN id: {no_match}', flush=True)

with open('public/kanji.json', 'w', encoding='utf-8') as f:
    json.dump(kanji_data, f, ensure_ascii=False, separators=(',', ':'))
size = os.path.getsize('public/kanji.json') // 1024
print(f'\nkanji.json saved ({size} KB)', flush=True)

# Spot-check
print('\nSpot checks:')
for lit in ['日', '一', '見', '食']:
    k = next(x for x in kanji_data if x['l'] == lit)
    if k.get('ex'):
        t = k['ex'].get('t', {}).get('en', '(no translation)')
        print(f'  {lit}  {k["ex"]["s"]}  ->  {t}')

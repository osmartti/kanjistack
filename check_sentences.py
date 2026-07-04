import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def kata_to_hira(t):
    return ''.join(chr(ord(c)-0x60) if 0x30A0<=ord(c)<=0x30F6 else c for c in t)

with open('public/kanji.json', encoding='utf-8') as f:
    data = json.load(f)

bad = []
for k in data:
    if not k.get('ex'):
        continue
    kanji_char = k['l']
    readings = set()
    for r in k.get('on', []):
        readings.add(kata_to_hira(r.replace('.','').replace('-','')))
    for r in k.get('kun', []):
        readings.add(r.replace('.','').replace('-',''))

    found = False
    for part in k['ex']['f']:
        if len(part) == 2:
            word, reading = part
            if kanji_char in word:
                if any(kr and kr in reading for kr in readings):
                    found = True
                    break
    if not found:
        bad.append((kanji_char, k['ex']['s'], sorted(readings)[:4]))

total_with_ex = sum(1 for k in data if k.get('ex'))
print(f'Bad sentences: {len(bad)} / {total_with_ex}')
for c, s, r in bad[:25]:
    print(f'  {c}  {r}  ->  {s}')

"""
build_vocab.py — builds public/vocab.json for KanjiStack vocabulary mode.

Sources:
  - elzup/jlpt-word-list (CSV, MIT) for word/reading/meaning/JLPT level
  - Tatoeba (jpn_sentences.tsv.bz2 + jpn_indices.tar.bz2 + eng_sentences.tsv.bz2)
    for example sentences (same files used by build_dual_examples.py)

Output schema per entry:
  { "w": str, "r": str, "m": [str, ...], "jlpt": int(1-5),
    "ex": { "s": str, "f": [[word, reading|null], ...], "t": {"en": str} } }
"""

import io, sys, json, re, csv, bz2, tarfile, urllib.request, random
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WORD_LIST_URL = (
    "https://raw.githubusercontent.com/elzup/jlpt-word-list/"
    "13aa3c54b27115be72d8a62cd4071077c68d2171/out/all.csv"
)
OUT_PATH = Path("public/vocab.json")

# JLPT tag → numeric level (5=N5 easiest … 1=N1 hardest)
# elzup uses the old 4-level system in tags; we map to 5-level manually.
# Old: JLPT_4 ≈ N5, JLPT_3 ≈ N4, JLPT_2 ≈ N3, JLPT_1 ≈ N1/N2
# New N5 tags may also appear as JLPT_5 in some merged datasets.
JLPT_TAG_MAP = {
    "JLPT_5": 5,
    "JLPT_4": 5,  # old N4/N5 block — treat as N5
    "JLPT_3": 4,  # old N3/N4 — treat as N4
    "JLPT_2": 3,  # old N2/N3 — treat as N3
    "JLPT_1": 2,  # old N1/N2 — treat as N2/N1
    "N5": 5, "N4": 4, "N3": 3, "N2": 2, "N1": 1,
}

KANJI_RE = re.compile(r"[\u4e00-\u9fff]")
KANJI_BLOCK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def has_kanji(s):
    return bool(KANJI_RE.search(s))


# ---------------------------------------------------------------------------
# 1. Download word list CSV
# ---------------------------------------------------------------------------
print("Downloading word list…")
with urllib.request.urlopen(WORD_LIST_URL) as resp:
    raw = resp.read().decode("utf-8")

reader = csv.DictReader(io.StringIO(raw))
vocab_raw = []
seen_words = set()
for row in reader:
    expr = row.get("expression", "").strip()
    reading = row.get("reading", "").strip()
    meaning = row.get("meaning", "").strip()
    tags = row.get("tags", "")
    if not expr or not reading or not meaning:
        continue
    # Skip if already seen (some words appear at multiple levels)
    key = (expr, reading)
    if key in seen_words:
        continue
    seen_words.add(key)

    # Determine JLPT level from tags
    level = None
    for part in tags.split():
        if part in JLPT_TAG_MAP:
            level = JLPT_TAG_MAP[part]
            break
    if level is None:
        continue  # skip entries with no JLPT tag

    # Clean up meaning — some have comma-separated alternatives in quotes
    meanings = [m.strip().strip('"') for m in meaning.split(",") if m.strip()]
    # Deduplicate while preserving order
    seen_m = set()
    deduped = []
    for m in meanings:
        if m.lower() not in seen_m:
            seen_m.add(m.lower())
            deduped.append(m)
    meanings = deduped[:5]  # cap at 5 meanings

    vocab_raw.append({"w": expr, "r": reading, "m": meanings, "jlpt": level})

# Sort: N5 (5) first → N1 (1) last
vocab_raw.sort(key=lambda x: -x["jlpt"])
print(f"Loaded {len(vocab_raw)} vocabulary entries.")

# ---------------------------------------------------------------------------
# 2. Load Tatoeba sentences
# ---------------------------------------------------------------------------
print("Loading Tatoeba sentences…")

jpn_sentences = {}  # id(int) → text
jpn_text_to_id = {}  # text → id(int)
eng_sentences = {}  # id(int) → text
jpn_to_eng = {}     # jpn_id(int) → eng_id(int)

JPN_BZ2 = "jpn_sentences.tsv.bz2"
ENG_BZ2 = "eng_sentences.tsv.bz2"
IDX_TAR = "jpn_indices.tar.bz2"

if Path(JPN_BZ2).exists():
    with bz2.open(JPN_BZ2, "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                sid = int(parts[0])
                text = parts[2]
                jpn_sentences[sid] = text
                jpn_text_to_id[text] = sid
    print(f"  {len(jpn_sentences)} Japanese sentences")
else:
    print(f"  {JPN_BZ2} not found — skipping example sentences")

if Path(ENG_BZ2).exists():
    with bz2.open(ENG_BZ2, "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                eng_sentences[int(parts[0])] = parts[2]
    print(f"  {len(eng_sentences)} English sentences")

if Path(IDX_TAR).exists():
    with tarfile.open(IDX_TAR, "r:bz2") as tar:
        f = tar.extractfile("jpn_indices.csv")
        for line in f:
            parts = line.decode("utf-8").rstrip("\n").split("\t")
            if len(parts) >= 2:
                jpn_id, eng_id = int(parts[0]), int(parts[1])
                if jpn_id not in jpn_to_eng:
                    jpn_to_eng[jpn_id] = eng_id
    print(f"  {len(jpn_to_eng)} translation links")

# ---------------------------------------------------------------------------
# 3. Furigana using pykakasi
# ---------------------------------------------------------------------------
try:
    import pykakasi
    kks = pykakasi.kakasi()
    HAS_KAKASI = True
    print("pykakasi available.")
except ImportError:
    HAS_KAKASI = False
    print("pykakasi not available — furigana will be skipped.")


def furigana_parts(text):
    """Return list of [surface, reading|None] pairs for `text`."""
    if not HAS_KAKASI:
        return [[text, None]]
    results = kks.convert(text)
    parts = []
    for item in results:
        orig = item["orig"]
        hira = item["hira"]
        if has_kanji(orig) and hira and hira != orig:
            parts.append([orig, hira])
        else:
            parts.append([orig, None])
    return parts


def find_example(word):
    """Find a short Tatoeba sentence containing `word`."""
    if not jpn_sentences:
        return None
    candidates = [
        sid for sid, text in jpn_sentences.items()
        if word in text and 10 <= len(text) <= 60
    ]
    if not candidates:
        return None
    random.seed(hash(word))
    sid = random.choice(candidates[:50] if len(candidates) > 50 else candidates)
    text = jpn_sentences[sid]
    trans = None
    eng_id = jpn_to_eng.get(sid)
    if eng_id and eng_id in eng_sentences:
        trans = eng_sentences[eng_id]
    f = furigana_parts(text)
    entry = {"s": text, "f": f}
    if trans:
        entry["t"] = {"en": trans}
    return entry


# ---------------------------------------------------------------------------
# 4. Build final vocab list
# ---------------------------------------------------------------------------
print("Building vocab.json…")
vocab = []
total = len(vocab_raw)
for i, entry in enumerate(vocab_raw):
    if i % 500 == 0:
        print(f"  {i}/{total}…")
    w = entry["w"]
    ex = find_example(w) if jpn_sentences else None
    out = {"w": w, "r": entry["r"], "m": entry["m"], "jlpt": entry["jlpt"]}
    if ex:
        out["ex"] = ex
    vocab.append(out)

OUT_PATH.write_text(
    json.dumps(vocab, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8"
)
ex_count = sum(1 for v in vocab if "ex" in v)
print(f"\nDone. {len(vocab)} entries, {ex_count} with example sentences → {OUT_PATH}")

# Level breakdown
from collections import Counter
levels = Counter(v["jlpt"] for v in vocab)
for lvl in sorted(levels, reverse=True):
    print(f"  N{lvl} (jlpt={lvl}): {levels[lvl]} words")

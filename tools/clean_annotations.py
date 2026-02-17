"""Small utility to clean backend/ml_dataset/annotations.jsonl

Removes annotations where `auto_crop` has width or height smaller
than a configured threshold (default 20 px). Backs up the original
file and writes a cleaned file at `annotations.cleaned.jsonl`.
"""
import json
import os
from datetime import datetime

DATA_DIR = os.path.join('backend', 'ml_dataset')
SRC_FILE = os.path.join(DATA_DIR, 'annotations.jsonl')
BACKUP_FMT = os.path.join(DATA_DIR, 'annotations.jsonl.bak.{ts}')
CLEANED_FILE = os.path.join(DATA_DIR, 'annotations.cleaned.jsonl')


def main(threshold: int = 20, overwrite: bool = False) -> dict:
    if not os.path.exists(SRC_FILE):
        raise FileNotFoundError(f"Source annotations file not found: {SRC_FILE}")

    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    backup_path = BACKUP_FMT.format(ts=ts)
    os.rename(SRC_FILE, backup_path)

    total = 0
    kept = 0
    removed = 0
    removed_examples = []

    with open(backup_path, 'r', encoding='utf-8') as inp, \
         open(CLEANED_FILE, 'w', encoding='utf-8') as outp:
        for line in inp:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except Exception:
                # preserve malformed lines? skip
                continue

            auto = obj.get('auto_crop') or {}
            w = int(auto.get('width') or 0)
            h = int(auto.get('height') or 0)

            if w < threshold or h < threshold:
                removed += 1
                removed_examples.append(obj.get('id') or obj.get('uuid') or '<no-id>')
                continue

            # keep
            kept += 1
            outp.write(json.dumps(obj, ensure_ascii=False) + '\n')

    # Optionally restore cleaned file to original path
    if overwrite:
        os.replace(CLEANED_FILE, SRC_FILE)

    result = {
        'source_backup': backup_path,
        'cleaned_file': CLEANED_FILE if not overwrite else SRC_FILE,
        'total': total,
        'kept': kept,
        'removed': removed,
        'removed_examples_sample': removed_examples[:10]
    }

    return result


if __name__ == '__main__':
    import pprint
    res = main()
    pprint.pprint(res)

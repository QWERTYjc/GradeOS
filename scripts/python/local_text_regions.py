"""Read local Tesseract line boxes from a complete page. No network access."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

from PIL import Image


def line_rows(tsv, width, height):
    lines = {}
    for word in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if word["level"] != "5" or not word["text"].strip():
            continue
        x, y, w, h = (int(word[key]) for key in ("left", "top", "width", "height"))
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
            continue
        key = tuple(word[k] for k in ("block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append((x, y, x + w, y + h, word["text"].strip()))
    rows = []
    for words in lines.values():
        left, top = min(w[0] for w in words), min(w[1] for w in words)
        right, bottom = max(w[2] for w in words), max(w[3] for w in words)
        rows.append({"rect": [left / width, top / height, (right-left) / width, (bottom-top) / height],
                     "candidates": [{"text": " ".join(w[4] for w in words)}]})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("documents", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    results = {}
    for student, document in json.loads(args.documents.read_text()).items():
        pages = []
        for page in document["pages"]:
            path = Path(page["absolute_path"])
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != page["sha256"]:
                raise ValueError("OCR source changed")
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
            result = subprocess.run(["tesseract", "stdin", "stdout", "tsv"], input=data,
                                    capture_output=True, check=True, timeout=90)
            pages.append({"page": page["page"], "source_sha256": page["sha256"],
                          "rows": line_rows(result.stdout.decode(), width, height)})
        results[student] = {"source_sha256": document["sha256"], "pages": pages}
    with args.output.open("x") as file:
        json.dump({"engine": "local Tesseract", "network_requests": 0, "documents": results}, file)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Report passages for the dashboard's "From NASA reports" answers.

Input:  data/reports/chunks_reports.jsonl — one chunk per PDF page of the NASA reports the dashboard cites
        (built on the Mac Mini by data/reports/build_corpus.py from hashed PDFs; verify() re-hashes them).
Output: data/report_passages.json — passages of about 600 characters cut at sentence ends, each with its
        document, page and exact page link. Table pages stay whole (up to 1,500 characters) so rows keep together.

The Mac Mini's retrieval test (Nov 13) found passages ranked with BM25 beat whole pages and page embeddings
for the airflow-cutoff question. Run after the report corpus is refreshed; build_all.py runs it.
"""
import json, re
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
TARGET = 600


def sentences(text):
    text = re.sub(r"-\n(?=[a-z])", "", text)            # join hyphenated line breaks
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return re.split(r"(?<=[.!?])\s+(?=[A-Z(\"“])", text)


def passages(text):
    out, cur = [], ""
    for s in sentences(text):
        if cur and len(cur) + len(s) > TARGET:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    # fold a very short tail into the previous passage
    if len(out) > 1 and len(out[-1]) < 150:
        tail = out.pop()
        out[-1] += " " + tail
    return out


def main():
    docs, rows = {}, []
    for line in (DATA / "reports" / "chunks_reports.jsonl").read_text().splitlines():
        c = json.loads(line)
        doc, page = c["id"].split(":page:")
        url = c["source"].split("#")[0]
        docs.setdefault(doc, {"name": c["acronym"], "url": url, "psi": c.get("psi"), "related": c.get("psi_related", [])})
        if c.get("quality") == "table":
            text = re.sub(r"[ \t]{2,}", "  ", c["text"]).strip()[:1500]
            rows.append([doc, int(page), text, 1])
        else:
            for p in passages(c["text"]):
                if len(p) >= 60:
                    rows.append([doc, int(page), p, 0])
    (DATA / "report_passages.json").write_text(json.dumps({"docs": docs, "passages": rows}, ensure_ascii=False, separators=(",", ":")))
    print(len(docs), "documents,", len(rows), "passages,", sum(len(r[2]) for r in rows) // 1000, "k characters")


if __name__ == "__main__":
    main()

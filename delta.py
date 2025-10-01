from datetime import datetime
from pathlib import Path
import csv
import re

def iso_now():
    """Timestamp for when a scrape runs."""
    return datetime.utcnow().isoformat()

def safe_slug(text):
    """File-system friendly slug for school names etc."""
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', (text or "").strip())

def list_delta(new_list, old_list):
    """Case-insensitive set difference for simple string lists."""
    new_set = { (x or "").strip() for x in (new_list or []) if x }
    old_set = { (x or "").strip() for x in (old_list or []) if x }
    return sorted(new_set - old_set, key=str.casefold)

def extract_pub_titles(pub_list):
    """Get a unique, sorted list of publication titles from list[dict]."""
    titles = []
    for p in pub_list or []:
        t = (p.get("title") or "").strip()
        if t:
            titles.append(t)
    return sorted(set(titles), key=str.casefold)

def normalize_interest_texts(interest_list):
    """Get the textual interest labels from list[dict]."""
    vals = []
    for d in interest_list or []:
        txt = (d.get("interest_text") or "").strip()
        if txt:
            vals.append(txt)
    return sorted(set(vals), key=str.casefold)

def write_delta_report(delta_rows, *, source: str, school: str | None, directory: str = ".") -> str:
    """
    Write CSV summarising changes detected in this scraping run.
    Returns the absolute file path.
    """
    Path(directory).mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    school_slug = safe_slug(school or "ALL")
    fname = f"delta_report_{source}_{school_slug}_{ts}.csv"
    fpath = str(Path(directory) / fname)

    # fixed column order so the file is predictable
    fieldnames = [
        "name", "school", "profileUrl", "source",
        "new_ai_skills", "new_expertise",
        "new_ai_interests", "new_publication_titles",
        "new_internal_collaborators", "scraped_at"
    ]

    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in delta_rows or []:
            # join list-y values as '|'
            out = row.copy()
            for k in ("new_ai_skills","new_expertise","new_ai_interests",
                      "new_publication_titles","new_internal_collaborators"):
                v = out.get(k)
                if isinstance(v, (list, tuple, set)):
                    out[k] = " | ".join(v)
            w.writerow(out)

    return str(Path(fpath).resolve())

def merge_csv_reports(paths, school, directory):
    """
    Merge multiple delta-report CSVs into a single CSV.
    Returns absolute path to the merged file.
    """
    # Filter to existing files only
    valid = [p for p in (paths or []) if p and Path(p).is_file()]
    if not valid:
        return ""

    # Read all rows, union headers
    rows = []
    headers = set()
    for p in valid:
        with open(p, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            headers.update(r.fieldnames or [])
            for row in r:
                rows.append(row)

    # Stable column order: keep the canonical fields first if present
    canonical = [
        "name", "school", "profileUrl", "source",
        "new_ai_skills", "new_expertise",
        "new_ai_interests", "new_publication_titles",
        "new_internal_collaborators", "scraped_at"
    ]
    # Add any extra headers encountered
    fieldnames = [h for h in canonical if h in headers] + [h for h in sorted(headers) if h not in canonical]

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    school_slug = safe_slug(school or "ALL")
    out_path = Path(directory) / f"delta_report_COMBINED_{school_slug}_{ts}.csv"

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})

    return str(out_path.resolve())

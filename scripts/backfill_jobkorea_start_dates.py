import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from crawler.database import DEFAULT_DB_PATH, init_database
from crawler.detail import extract_start_date_from_text


def main():
    init_database()
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT id, raw_detail_text
        FROM job_postings
        WHERE source = 'jobkorea'
          AND detail_status = 'success'
          AND raw_detail_text IS NOT NULL
          AND raw_detail_text != ''
        """
    ).fetchall()

    found = 0
    samples = []
    for row in rows:
        start_date = extract_start_date_from_text(row["raw_detail_text"])
        if not start_date:
            continue

        conn.execute(
            "UPDATE job_postings SET posted_date = ? WHERE id = ?",
            (start_date, row["id"]),
        )
        found += 1
        if len(samples) < 5:
            samples.append(f"{row['id']}:{start_date}")

    conn.commit()
    conn.close()

    print(f"checked={len(rows)}")
    print(f"found={found}")
    print("samples=" + "; ".join(samples))


if __name__ == "__main__":
    main()

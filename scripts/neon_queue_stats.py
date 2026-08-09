import json
import os
from datetime import datetime, timezone

import psycopg


database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL is required")

with psycopg.connect(database_url) as conn, conn.cursor() as cur:
    reset_count = 0
    if os.environ.get("RESET_PROCESSING") == "true":
        cur.execute(
            """
            UPDATE detail_fetch_queue
            SET status='QUEUED', lease_until=NULL, next_attempt_at=NOW(),
                last_error='운영자 리셋: 정체 실행 취소', updated_at=NOW()
            WHERE status='PROCESSING'
            """
        )
        reset_count = cur.rowcount
        conn.commit()
    cur.execute(
        """
        SELECT
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE q.status = 'SUCCESS') AS success,
          COUNT(*) FILTER (WHERE q.status = 'PROCESSING') AS processing,
          COUNT(*) FILTER (WHERE q.status = 'QUEUED') AS queued,
          COUNT(*) FILTER (WHERE q.status = 'FAILED') AS failed,
          COUNT(*) FILTER (WHERE p.detail_status = 'success') AS detail_success,
          MIN(q.created_at), MAX(q.updated_at)
        FROM detail_fetch_queue q
        JOIN job_postings p ON p.id = q.job_posting_id
        """
    )
    row = cur.fetchone()

print(json.dumps({
    "measured_at": datetime.now(timezone.utc).isoformat(),
    "reset_count": reset_count,
    "total": row[0], "success": row[1], "processing": row[2],
    "queued": row[3], "failed": row[4], "detail_success": row[5],
    "oldest_queue_at": row[6].isoformat() if row[6] else None,
    "latest_update_at": row[7].isoformat() if row[7] else None,
}, ensure_ascii=False))

"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";

export function formatSnapshotUpdatedAt(value: string | null) {
  return value?.replace(/\s+KST$/, "") ?? null;
}

export default function SnapshotUpdatedAt() {
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    api.snapshotUpdatedAt()
      .then((value) => setUpdatedAt(formatSnapshotUpdatedAt(value)))
      .catch(() => setUpdatedAt(null));
  }, []);

  return (
    <span className="snapshotUpdatedAt">
      마지막 업데이트: {updatedAt ?? "확인 중"}
    </span>
  );
}

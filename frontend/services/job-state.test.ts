import { describe, expect, it } from "vitest";

import {
  V1_DISLIKED_KEY,
  V1_FAVORITES_KEY,
  V1_VIEWED_KEY,
  V2_METADATA_KEY,
  V2_USER_STATE_KEY,
  checksumState,
  getStableJobKey,
  getMissingFavoriteSnapshots,
  migrateUserStorageV2,
  readUserState,
  sanitizeUserState,
  updateUserInteraction,
} from "./job-state";

class MemoryStorage {
  private values = new Map<string, string>();

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}

const jobs = [
  { id: 1, stable_key: "jobkorea:100", detail_url: "/Recruit/GI_Read/100" },
  { id: 2, stable_key: "jobkorea:200", detail_url: "/Recruit/GI_Read/200" },
];

describe("stable job state", () => {
  it("migrates favorites, memos, statuses, disliked and viewed state with backups", () => {
    const storage = new MemoryStorage();
    storage.setItem(V1_FAVORITES_KEY, JSON.stringify({ 1: { memo: "지원 예정", status: "planned" } }));
    storage.setItem(V1_DISLIKED_KEY, JSON.stringify([2]));
    storage.setItem(V1_VIEWED_KEY, JSON.stringify([1, 2]));

    const metadata = migrateUserStorageV2(storage, { 1: "jobkorea:100", 2: "jobkorea:200" });
    const state = readUserState(storage);

    expect(state["jobkorea:100"]).toMatchObject({
      isFavorite: true,
      isDisliked: false,
      isViewed: true,
      memo: "지원 예정",
      status: "planned",
    });
    expect(state["jobkorea:200"]).toMatchObject({ isDisliked: true, isViewed: true });
    expect(storage.getItem(`${V1_FAVORITES_KEY}_backup_v1`)).toBe(storage.getItem(V1_FAVORITES_KEY));
    expect(metadata?.checksum).toBe(checksumState(storage.getItem(V2_USER_STATE_KEY) ?? ""));
    expect(JSON.parse(storage.getItem(V2_METADATA_KEY) ?? "{}").migration_version).toBe(2);
  });

  it("keeps state attached to the same posting when snapshot order changes", () => {
    const storage = new MemoryStorage();
    updateUserInteraction(storage, getStableJobKey(jobs[0]), () => ({ isFavorite: true, memo: "A" }));

    const reordered = [...jobs].reverse();
    const state = readUserState(storage);
    expect(state[getStableJobKey(reordered[1])]?.memo).toBe("A");
    expect(state[getStableJobKey(reordered[0])]).toBeUndefined();
  });

  it("is not shifted by a newly inserted posting", () => {
    const storage = new MemoryStorage();
    updateUserInteraction(storage, "jobkorea:200", () => ({ isDisliked: true }));

    const inserted = [
      { id: 1, stable_key: "jobkorea:300" },
      { id: 2, stable_key: "jobkorea:100" },
      { id: 3, stable_key: "jobkorea:200" },
    ];
    const state = readUserState(storage);
    expect(state[getStableJobKey(inserted[2])]?.isDisliked).toBe(true);
    expect(state[getStableJobKey(inserted[0])]).toBeUndefined();
  });

  it("restores state when a temporarily missing posting returns", () => {
    const storage = new MemoryStorage();
    updateUserInteraction(storage, "jobkorea:100", () => ({ isFavorite: true, memo: "복구됨" }));

    const stateWhileMissing = readUserState(storage);
    expect(Object.keys(stateWhileMissing)).toContain("jobkorea:100");

    const returnedJob = { id: 99, source: "jobkorea", source_job_id: "100" };
    expect(stateWhileMissing[getStableJobKey(returnedJob)]?.memo).toBe("복구됨");
  });

  it("repairs a favorite that was incorrectly persisted as excluded or disliked", () => {
    const { state, changed } = sanitizeUserState({
      "jobkorea:100": {
        isFavorite: true,
        isDisliked: true,
        status: "excluded",
        memo: "지원 예정 공고",
      },
      "jobkorea:200": { isFavorite: false, isDisliked: true, status: "excluded" },
    });

    expect(changed).toBe(true);
    expect(state["jobkorea:100"]).toMatchObject({
      isFavorite: true,
      isDisliked: false,
      status: "planned",
      memo: "지원 예정 공고",
    });
    expect(state["jobkorea:200"]).toMatchObject({ isDisliked: true, status: "excluded" });
  });

  it("does not rewrite already valid favorite state", () => {
    const original = { "jobkorea:100": { isFavorite: true, isDisliked: false, status: "applied" } };
    const result = sanitizeUserState(original);
    expect(result.changed).toBe(false);
    expect(result.state).toEqual(original);
  });

  it("keeps the full saved posting available after it disappears from a refreshed snapshot", () => {
    const storage = new MemoryStorage();
    updateUserInteraction(storage, "jobkorea:100", () => ({
      isFavorite: true,
      memo: "마감 후에도 확인",
      jobSnapshot: {
        id: 1,
        stable_key: "jobkorea:100",
        title: "저장한 개발자 공고",
        deadline_date: "2026-08-01",
      },
    }));

    const missing = getMissingFavoriteSnapshots(readUserState(storage), new Set(["jobkorea:200"]));
    expect(missing).toHaveLength(1);
    expect(missing[0]).toMatchObject({
      stable_key: "jobkorea:100",
      title: "저장한 개발자 공고",
      deadline_date: "2026-08-01",
    });
    expect(getMissingFavoriteSnapshots(readUserState(storage), new Set(["jobkorea:100"]))).toEqual([]);
  });

  it("does not overwrite a valid completed migration", () => {
    const storage = new MemoryStorage();
    storage.setItem(V1_DISLIKED_KEY, JSON.stringify([1]));
    migrateUserStorageV2(storage, { 1: "jobkorea:100" });
    storage.setItem(V1_DISLIKED_KEY, JSON.stringify([2]));

    migrateUserStorageV2(storage, { 2: "jobkorea:200" });
    expect(readUserState(storage)["jobkorea:100"]?.isDisliked).toBe(true);
    expect(readUserState(storage)["jobkorea:200"]).toBeUndefined();
  });
});

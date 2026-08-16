export const V1_FAVORITES_KEY = "job-radar-demo-favorites";
export const V1_DISLIKED_KEY = "job-radar-disliked-jobs";
export const V1_VIEWED_KEY = "job-radar-viewed-jobs";
export const V2_USER_STATE_KEY = "job-radar-user-state-v2";
export const V2_METADATA_KEY = "job-radar-migration-meta-v2";
export const FAVORITE_POLLUTION_REPAIR_KEY = "job-radar-repair-disliked-favorites-v1";

const MIGRATION_VERSION = 2;
const TEMP_STATE_KEY = `${V2_USER_STATE_KEY}-pending`;

export type JobIdentity = {
  id: number;
  source?: string;
  source_job_id?: string;
  stable_key?: string;
  detail_url?: string | null;
};

export type UserInteraction = {
  isFavorite?: boolean;
  isDisliked?: boolean;
  isViewed?: boolean;
  isDeleted?: boolean;
  memo?: string;
  status?: string;
  updatedAt?: string;
  jobSnapshot?: JobIdentity & Record<string, unknown>;
};

export type UserState = Record<string, UserInteraction>;

export type MigrationMetadata = {
  migration_version: number;
  completed_at: string;
  checksum: string;
  converted_count: number;
  skipped_count: number;
  conflict_count: number;
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;
type RemovableStorageLike = Pick<Storage, "removeItem">;

function parseJson<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function getStableJobKey(job: JobIdentity): string {
  if (job.stable_key) return job.stable_key;
  if (job.source_job_id) return `${job.source || "jobkorea"}:${job.source_job_id}`;
  const sourceJobId = job.detail_url?.match(/\/GI_Read\/(\d+)/)?.[1];
  return sourceJobId ? `jobkorea:${sourceJobId}` : `legacy:${job.id}`;
}

export function checksumState(serializedState: string): string {
  let hash = 2166136261;
  for (let index = 0; index < serializedState.length; index += 1) {
    hash ^= serializedState.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

export function readUserState(storage: StorageLike): UserState {
  return parseJson<UserState>(storage.getItem(V2_USER_STATE_KEY), {});
}

export function sanitizeUserState(state: UserState): { state: UserState; changed: boolean } {
  let changed = false;
  const sanitized = Object.fromEntries(Object.entries(state).map(([stableKey, interaction]) => {
    if (interaction.isFavorite && (interaction.status === "excluded" || interaction.isDisliked)) {
      changed = true;
      return [stableKey, {
        ...interaction,
        isDisliked: false,
        status: "planned",
      }];
    }
    return [stableKey, interaction];
  }));
  return { state: sanitized, changed };
}

export function repairPollutedDislikedFavorites(storage: StorageLike): number {
  if (storage.getItem(FAVORITE_POLLUTION_REPAIR_KEY) === "complete") return 0;

  const state = readUserState(storage);
  let repairedCount = 0;
  const repaired = Object.fromEntries(Object.entries(state).map(([stableKey, interaction]) => {
    const pollutedByPreviousMigration = interaction.isFavorite
      && !interaction.isDisliked
      && !interaction.isDeleted
      && interaction.status === "planned"
      && interaction.memo === undefined;
    if (!pollutedByPreviousMigration) return [stableKey, interaction];
    repairedCount += 1;
    return [stableKey, {
      ...interaction,
      isFavorite: false,
      isDisliked: true,
      status: undefined,
      jobSnapshot: undefined,
    }];
  }));

  if (repairedCount > 0) writeUserState(storage, repaired);
  storage.setItem(FAVORITE_POLLUTION_REPAIR_KEY, "complete");
  return repairedCount;
}

export function resetUserStorage(storage: RemovableStorageLike) {
  const keys = [
    V1_FAVORITES_KEY,
    V1_DISLIKED_KEY,
    V1_VIEWED_KEY,
    V2_USER_STATE_KEY,
    V2_METADATA_KEY,
    FAVORITE_POLLUTION_REPAIR_KEY,
    TEMP_STATE_KEY,
  ];
  keys.forEach((key) => {
    storage.removeItem(key);
    storage.removeItem(`${key}_backup_v1`);
  });
}

export function getMissingFavoriteSnapshots(
  state: UserState,
  currentStableKeys: Set<string>,
): Array<JobIdentity & Record<string, unknown>> {
  return Object.entries(state).flatMap(([stableKey, interaction]) => {
    const snapshot = interaction.jobSnapshot;
    if (!interaction.isFavorite || !snapshot || currentStableKeys.has(stableKey)) return [];
    return [{ ...snapshot, stable_key: stableKey }];
  });
}

export function writeUserState(storage: StorageLike, state: UserState): void {
  storage.setItem(V2_USER_STATE_KEY, JSON.stringify(state));
}

export function updateUserInteraction(
  storage: StorageLike,
  stableKey: string,
  update: (current: UserInteraction) => UserInteraction | null,
): UserState {
  const state = readUserState(storage);
  const nextInteraction = update(state[stableKey] ?? {});
  if (nextInteraction) state[stableKey] = { ...nextInteraction, updatedAt: new Date().toISOString() };
  else delete state[stableKey];
  writeUserState(storage, state);
  return state;
}

export function migrateUserStorageV2(
  storage: StorageLike,
  legacyIdToStableKeyMap: Record<number, string>,
): MigrationMetadata | null {
  const existingState = storage.getItem(V2_USER_STATE_KEY);
  const existingMeta = parseJson<MigrationMetadata | null>(storage.getItem(V2_METADATA_KEY), null);
  if (existingState && existingMeta?.migration_version === MIGRATION_VERSION) {
    return existingMeta;
  }

  for (const key of [V1_FAVORITES_KEY, V1_DISLIKED_KEY, V1_VIEWED_KEY, V2_USER_STATE_KEY]) {
    const value = storage.getItem(key);
    if (value !== null) storage.setItem(`${key}_backup_v1`, value);
  }

  const v2State: UserState = existingState ? parseJson<UserState>(existingState, {}) : {};
  const favorites = parseJson<Record<string, { memo?: string; status?: string }>>(
    storage.getItem(V1_FAVORITES_KEY),
    {},
  );
  const disliked = parseJson<number[]>(storage.getItem(V1_DISLIKED_KEY), []);
  const viewed = parseJson<number[]>(storage.getItem(V1_VIEWED_KEY), []);
  let skippedCount = 0;
  let conflictCount = 0;

  for (const [legacyId, favorite] of Object.entries(favorites)) {
    const stableKey = legacyIdToStableKeyMap[Number(legacyId)];
    if (!stableKey) {
      skippedCount += 1;
      continue;
    }
    v2State[stableKey] = {
      ...v2State[stableKey],
      isFavorite: true,
      isDisliked: false,
      memo: favorite?.memo ?? "",
      status: favorite?.status ?? "planned",
    };
  }

  for (const legacyId of disliked) {
    const stableKey = legacyIdToStableKeyMap[legacyId];
    if (!stableKey) {
      skippedCount += 1;
      continue;
    }
    if (v2State[stableKey]?.isFavorite) {
      conflictCount += 1;
      continue;
    }
    v2State[stableKey] = { ...v2State[stableKey], isDisliked: true };
  }

  for (const legacyId of viewed) {
    const stableKey = legacyIdToStableKeyMap[legacyId];
    if (!stableKey) {
      skippedCount += 1;
      continue;
    }
    v2State[stableKey] = { ...v2State[stableKey], isViewed: true };
  }

  const serializedState = JSON.stringify(v2State);
  storage.setItem(TEMP_STATE_KEY, serializedState);
  if (storage.getItem(TEMP_STATE_KEY) !== serializedState) {
    throw new Error("V2 사용자 상태 임시 기록 검증에 실패했습니다.");
  }
  storage.setItem(V2_USER_STATE_KEY, serializedState);

  const metadata: MigrationMetadata = {
    migration_version: MIGRATION_VERSION,
    completed_at: new Date().toISOString(),
    checksum: checksumState(serializedState),
    converted_count: Object.keys(v2State).length,
    skipped_count: skippedCount,
    conflict_count: conflictCount,
  };
  storage.setItem(V2_METADATA_KEY, JSON.stringify(metadata));
  return metadata;
}

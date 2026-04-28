from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, Sequence

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)


class SqliteCheckpointSaver(BaseCheckpointSaver[str]):
    def __init__(self, path: str, *, serde=None) -> None:
        super().__init__(serde=serde)
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    checkpoint_type TEXT NOT NULL,
                    checkpoint_blob BLOB NOT NULL,
                    metadata_type TEXT NOT NULL,
                    metadata_blob BLOB NOT NULL,
                    parent_checkpoint_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                );
                CREATE TABLE IF NOT EXISTS checkpoint_blobs (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    version TEXT NOT NULL,
                    value_type TEXT NOT NULL,
                    value_blob BLOB NOT NULL,
                    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
                );
                CREATE TABLE IF NOT EXISTS checkpoint_writes (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    write_idx INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    value_type TEXT NOT NULL,
                    value_blob BLOB NOT NULL,
                    task_path TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx)
                );
                """
            )

    def _load_blobs(self, conn: sqlite3.Connection, thread_id: str, checkpoint_ns: str, versions: ChannelVersions) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for channel, version in versions.items():
            row = conn.execute(
                "SELECT value_type, value_blob FROM checkpoint_blobs WHERE thread_id = ? AND checkpoint_ns = ? AND channel = ? AND version = ?",
                (thread_id, checkpoint_ns, channel, str(version)),
            ).fetchone()
            if row and row['value_type'] != 'empty':
                values[channel] = self.serde.loads_typed((row['value_type'], row['value_blob']))
        return values

    def _build_tuple(self, conn: sqlite3.Connection, row: sqlite3.Row) -> CheckpointTuple:
        thread_id = row['thread_id']
        checkpoint_ns = row['checkpoint_ns']
        checkpoint_id = row['checkpoint_id']
        checkpoint = self.serde.loads_typed((row['checkpoint_type'], row['checkpoint_blob']))
        metadata = self.serde.loads_typed((row['metadata_type'], row['metadata_blob']))
        writes = conn.execute(
            "SELECT task_id, channel, value_type, value_blob, task_path FROM checkpoint_writes WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ? ORDER BY task_id, write_idx",
            (thread_id, checkpoint_ns, checkpoint_id),
        ).fetchall()
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id}},
            checkpoint={
                **checkpoint,
                "channel_values": self._load_blobs(conn, thread_id, checkpoint_ns, checkpoint["channel_versions"]),
            },
            metadata=metadata,
            parent_config=(
                {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": row['parent_checkpoint_id']}}
                if row['parent_checkpoint_id']
                else None
            ),
            pending_writes=[
                (write['task_id'], write['channel'], self.serde.loads_typed((write['value_type'], write['value_blob'])))
                for write in writes
            ],
        )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config['configurable']['thread_id']
        checkpoint_ns = config['configurable'].get('checkpoint_ns', '')
        checkpoint_id = get_checkpoint_id(config)
        with self._connect() as conn:
            if checkpoint_id:
                row = conn.execute(
                    "SELECT * FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
                    (thread_id, checkpoint_ns, checkpoint_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? ORDER BY checkpoint_id DESC LIMIT 1",
                    (thread_id, checkpoint_ns),
                ).fetchone()
            if not row:
                return None
            return self._build_tuple(conn, row)

    def list(self, config: RunnableConfig | None, *, filter: dict[str, Any] | None = None, before: RunnableConfig | None = None, limit: int | None = None) -> Iterator[CheckpointTuple]:
        with self._connect() as conn:
            params: list[Any] = []
            query = "SELECT * FROM checkpoints WHERE 1=1"
            if config:
                query += " AND thread_id = ?"
                params.append(config['configurable']['thread_id'])
                checkpoint_ns = config['configurable'].get('checkpoint_ns')
                if checkpoint_ns is not None:
                    query += " AND checkpoint_ns = ?"
                    params.append(checkpoint_ns)
                checkpoint_id = get_checkpoint_id(config)
                if checkpoint_id:
                    query += " AND checkpoint_id = ?"
                    params.append(checkpoint_id)
            if before and get_checkpoint_id(before):
                query += " AND checkpoint_id < ?"
                params.append(get_checkpoint_id(before))
            query += " ORDER BY checkpoint_id DESC"
            if limit is not None:
                query += f" LIMIT {int(limit)}"
            for row in conn.execute(query, params).fetchall():
                item = self._build_tuple(conn, row)
                if filter and not all(item.metadata.get(k) == v for k, v in filter.items()):
                    continue
                yield item

    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        thread_id = config['configurable']['thread_id']
        checkpoint_ns = config['configurable'].get('checkpoint_ns', '')
        checkpoint_copy = checkpoint.copy()
        values = checkpoint_copy.pop('channel_values')
        checkpoint_type, checkpoint_blob = self.serde.dumps_typed(checkpoint_copy)
        metadata_type, metadata_blob = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
        with self._connect() as conn:
            for channel, version in new_versions.items():
                if channel in values:
                    value_type, value_blob = self.serde.dumps_typed(values[channel])
                else:
                    value_type, value_blob = ('empty', b'')
                conn.execute(
                    "INSERT OR REPLACE INTO checkpoint_blobs (thread_id, checkpoint_ns, channel, version, value_type, value_blob) VALUES (?, ?, ?, ?, ?, ?)",
                    (thread_id, checkpoint_ns, channel, str(version), value_type, value_blob),
                )
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, checkpoint_type, checkpoint_blob, metadata_type, metadata_blob, parent_checkpoint_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    thread_id,
                    checkpoint_ns,
                    checkpoint['id'],
                    checkpoint_type,
                    checkpoint_blob,
                    metadata_type,
                    metadata_blob,
                    config['configurable'].get('checkpoint_id'),
                ),
            )
        return {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint['id']}}

    def put_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = '') -> None:
        thread_id = config['configurable']['thread_id']
        checkpoint_ns = config['configurable'].get('checkpoint_ns', '')
        checkpoint_id = config['configurable']['checkpoint_id']
        with self._connect() as conn:
            for idx, (channel, value) in enumerate(writes):
                write_idx = WRITES_IDX_MAP.get(channel, idx)
                value_type, value_blob = self.serde.dumps_typed(value)
                conn.execute(
                    "INSERT OR REPLACE INTO checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx, channel, value_type, value_blob, task_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx, channel, value_type, value_blob, task_path),
                )

    def delete_thread(self, thread_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM checkpoint_blobs WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (thread_id,))

    def delete_for_runs(self, run_ids: Sequence[str]) -> None:
        for run_id in run_ids:
            self.delete_thread(run_id)

    def copy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        raise NotImplementedError('copy_thread is not implemented for SqliteCheckpointSaver')

    def prune(self, thread_ids: Sequence[str], *, strategy: str = 'keep_latest') -> None:
        if strategy == 'delete':
            for thread_id in thread_ids:
                self.delete_thread(thread_id)
            return
        if strategy != 'keep_latest':
            raise ValueError(f'Unsupported prune strategy: {strategy}')
        with self._connect() as conn:
            for thread_id in thread_ids:
                rows = conn.execute(
                    "SELECT thread_id, checkpoint_ns, checkpoint_id FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_ns, checkpoint_id DESC",
                    (thread_id,),
                ).fetchall()
                keep: set[tuple[str, str, str]] = set()
                seen_ns: set[str] = set()
                for row in rows:
                    ns = row['checkpoint_ns']
                    if ns in seen_ns:
                        conn.execute(
                            "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
                            (row['thread_id'], ns, row['checkpoint_id']),
                        )
                        conn.execute(
                            "DELETE FROM checkpoint_writes WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
                            (row['thread_id'], ns, row['checkpoint_id']),
                        )
                    else:
                        seen_ns.add(ns)
                        keep.add((row['thread_id'], ns, row['checkpoint_id']))

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return self.get_tuple(config)

    async def alist(self, config: RunnableConfig | None, *, filter: dict[str, Any] | None = None, before: RunnableConfig | None = None, limit: int | None = None) -> AsyncIterator[CheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = '') -> None:
        self.put_writes(config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        self.delete_thread(thread_id)

    async def adelete_for_runs(self, run_ids: Sequence[str]) -> None:
        self.delete_for_runs(run_ids)

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        self.copy_thread(source_thread_id, target_thread_id)

    async def aprune(self, thread_ids: Sequence[str], *, strategy: str = 'keep_latest') -> None:
        self.prune(thread_ids, strategy=strategy)

    def get_next_version(self, current: str | None, channel: None) -> str:
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(str(current).split('.')[0])
        return f"{current_v + 1:032}.0000000000000000"

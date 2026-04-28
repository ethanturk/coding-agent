from pathlib import Path

from app.services.langgraph_checkpoint import SqliteCheckpointSaver


def test_sqlite_checkpoint_saver_round_trip(tmp_path):
    db_path = tmp_path / 'checkpoints.sqlite3'
    saver = SqliteCheckpointSaver(str(db_path))
    config = {'configurable': {'thread_id': 'thread-1', 'checkpoint_ns': ''}}
    checkpoint = {
        'v': 1,
        'id': 'cp-1',
        'ts': '2026-04-28T00:00:00Z',
        'channel_values': {'messages': [{'role': 'user', 'content': 'hi'}]},
        'channel_versions': {'messages': '00000000000000000000000000000001.0000000000000000'},
        'versions_seen': {},
        'updated_channels': ['messages'],
    }
    metadata = {'source': 'input', 'step': -1, 'parents': {}, 'run_id': 'run-1'}
    saver.put(config, checkpoint, metadata, checkpoint['channel_versions'])
    loaded = saver.get_tuple({'configurable': {'thread_id': 'thread-1', 'checkpoint_ns': ''}})
    assert loaded is not None
    assert loaded.checkpoint['id'] == 'cp-1'
    assert loaded.checkpoint['channel_values']['messages'][0]['content'] == 'hi'
    assert loaded.metadata['run_id'] == 'run-1'

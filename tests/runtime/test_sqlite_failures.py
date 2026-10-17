"""Ledger errors are recoverable domain failures; no remote provider involved."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
from generation_tasks import GenerationStore, GenerationError
from model_text_generic import TextCallStore, ModelTextError
from deepseek_text import DeepSeekCallStore, DeepSeekError


@pytest.mark.parametrize('store,error', [(GenerationStore, GenerationError),
    (TextCallStore, ModelTextError), (DeepSeekCallStore, DeepSeekError)])
def test_corrupt_store_is_domain_failure(tmp_path, store, error):
    path = tmp_path / 'bad.sqlite3'
    path.write_bytes(b'not sqlite')
    with pytest.raises(error, match='STORE_ERROR'):
        store(path)


@pytest.mark.parametrize('store,error', [(GenerationStore, GenerationError),
    (TextCallStore, ModelTextError), (DeepSeekCallStore, DeepSeekError)])
def test_locked_store_is_domain_failure(tmp_path, monkeypatch, store, error):
    path = tmp_path / 'locked.sqlite3'
    store(path)
    connect = sqlite3.connect
    def fast_connect(*args, **kwargs):
        kwargs['timeout'] = 0.01
        return connect(*args, **kwargs)
    monkeypatch.setattr(sqlite3, 'connect', fast_connect)
    with connect(path) as holder:
        holder.execute('BEGIN EXCLUSIVE')
        with pytest.raises(error, match='STORE_ERROR'):
            store(path)

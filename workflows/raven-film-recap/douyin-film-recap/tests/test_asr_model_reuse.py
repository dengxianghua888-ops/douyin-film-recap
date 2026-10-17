from types import SimpleNamespace

from douyin_film_recap import asr


def test_multiple_sources_share_one_stage_local_model(app_config, monkeypatch):
    created, consumed = [], []
    def load(config):
        model = object()
        created.append(model)
        return model
    def transcribe(path, source_id, config, *, model):
        consumed.append((source_id, model))
        return []
    monkeypatch.setattr(asr, '_load_whisper_model', load)
    monkeypatch.setattr(asr, 'transcribe_with_faster_whisper', transcribe)
    manifest = SimpleNamespace(sources=[SimpleNamespace(source_id=str(i), subtitle_path=None,
        has_audio=True, path=f'{i}.mp4', order=i, fingerprint=str(i)) for i in range(3)])
    asr.build_transcript(manifest, app_config)
    assert len(created) == 1
    assert len(consumed) == 3
    assert all(model is created[0] for _, model in consumed)
    asr.build_transcript(manifest, app_config)
    assert len(created) == 2


def test_no_audio_does_not_load_optional_model(app_config, monkeypatch):
    monkeypatch.setattr(asr, '_load_whisper_model', lambda _: (_ for _ in ()).throw(AssertionError('loaded')))
    asr.build_transcript(SimpleNamespace(sources=[]), app_config)

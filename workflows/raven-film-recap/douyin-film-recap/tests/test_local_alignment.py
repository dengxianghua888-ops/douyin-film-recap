"""Engineering-only fixtures: random self-created weights and synthesized tones.

No trained acoustic model, licensed speech sample or Chinese accuracy evaluation.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import wave

import numpy as np
import pytest
from typer.testing import CliRunner

from douyin_film_recap import local_alignment as local
from douyin_film_recap.alignment import import_alignment
from douyin_film_recap.asr import parse_subtitle
from douyin_film_recap.cli import app
from douyin_film_recap.models import SourceInfo, SourceManifest
from douyin_film_recap.utils import content_identity


def emissions(ids, vocab=4):
    probs = np.full((len(ids), vocab), .01)
    probs[np.arange(len(ids)), ids] = .97
    return np.log(probs / probs.sum(axis=1, keepdims=True))


def test_native_frames_and_repeated_label_blank():
    spans = local.ctc_spans(emissions([0, 1, 1, 0, 1, 2, 0]), [1, 1, 2], 0)
    assert [s[:2] for s in spans] == [(1, 3), (4, 5), (5, 6)]
    assert all(0 < s[2] < 1 for s in spans)
    with pytest.raises(ValueError, match="Insufficient"):
        local.ctc_spans(emissions([1, 1]), [1, 1], 0)


def test_frame_cells_use_convolution_geometry_and_samples():
    edges = local.frame_edges(100, [10, 3], [5, 2], 9)
    assert np.array_equal(edges, [0, 15, 25, 35, 45, 55, 65, 75, 85, 100])
    with pytest.raises(ValueError, match="geometry"):
        local.frame_edges(100, [10, 3], [5, 2], 10)


@pytest.mark.parametrize("value", [float('nan'), float('inf')])
def test_nonfinite_emissions_rejected(value):
    x = emissions([0, 1]); x[0, 0] = value
    with pytest.raises(ValueError, match="finite"):
        local.ctc_spans(x, [1], 0)


def test_cli_and_default_import_do_not_import_torch():
    check = subprocess.run([sys.executable, '-c',
        'import sys; from douyin_film_recap.cli import app; '
        'assert "torch" not in sys.modules; assert "transformers" not in sys.modules'],
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(Path(local.__file__).parents[1])})
    assert check.returncode == 0, check.stderr
    assert CliRunner().invoke(app, ['run-local-alignment', '--help']).exit_code == 0


@pytest.fixture
def tiny_model(tmp_path, monkeypatch):
    torch = pytest.importorskip('torch')
    pytest.importorskip('transformers')
    from transformers import Wav2Vec2Config, Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC
    def deny(*args, **kwargs):
        raise AssertionError('No network permitted during model creation or execution')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)
    torch.manual_seed(123)
    torch.set_num_threads(1)
    model = tmp_path / 'model'; model.mkdir()
    config = Wav2Vec2Config(vocab_size=5, hidden_size=8, num_hidden_layers=1,
        num_attention_heads=2, intermediate_size=16, conv_dim=(8, 8, 8),
        conv_stride=(5, 2, 2), conv_kernel=(10, 3, 3), num_conv_pos_embeddings=8,
        num_conv_pos_embedding_groups=2, pad_token_id=0, bos_token_id=None,
        eos_token_id=None, mask_time_prob=0.0, apply_spec_augment=False)
    Wav2Vec2ForCTC(config).save_pretrained(model, safe_serialization=True)
    Wav2Vec2FeatureExtractor(sampling_rate=16000, return_attention_mask=False).save_pretrained(model)
    (model / 'vocab.json').write_text(json.dumps({'<pad>': 0, '你': 1, '好': 2, '1': 3, 'a': 4}))
    return model


@pytest.fixture
def source(tmp_path):
    media = tmp_path / 'owned-tone.wav'
    # A non-speech signal generated here. 22.05 kHz checks real FFmpeg resampling.
    samples = (np.sin(np.arange(22050) / 22050 * 2 * np.pi * 440) * 12000).astype('<i2')
    with wave.open(str(media), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(22050)
        wav.writeframes(samples.tobytes())
    subtitle = tmp_path / 'owned-tone.srt'
    subtitle.write_text('1\n00:00:00,000 --> 00:00:00,200\n你好\n\n'
                        '2\n00:00:00,500 --> 00:00:00,800\n你你好1a\n', encoding='utf-8')
    return SourceInfo(source_id='test', path=str(media), filename=media.name,
        fingerprint=content_identity(media)['sha256'], duration=1., width=16, height=16,
        fps=25, subtitle_path=str(subtitle), subtitle_fingerprint=content_identity(subtitle)['sha256'])


def execute(source, tiny_model, tmp_path, **overrides):
    options = dict(source=source, cue_indices=[1], model_dir=tiny_model,
        model_sha256=local.model_identity(tiny_model), output=tmp_path/'alignment.json')
    options.update(overrides)
    return local.run_local_alignment(**options)


def test_real_tiny_model_forward_selected_window_offset_and_cache(source, tiny_model, tmp_path, monkeypatch):
    calls = []
    original = local._audio_window
    def window(*args):
        calls.append(args[2:])
        return original(*args)
    monkeypatch.setattr(local, '_audio_window', window)
    original_hash = content_identity(source.path)
    report = execute(source, tiny_model, tmp_path, cache_dir=tmp_path/'cache')
    assert report['cache_hit'] is False and report['aligned_cues'] == 1
    assert len(calls) == 1 and calls[0] == pytest.approx((.5, .3))
    result = json.loads((tmp_path/'alignment.json').read_text())
    assert [c['cue_index'] for c in result['cues']] == [1]
    tokens = result['cues'][0]['tokens']
    assert ''.join(t['text'] for t in tokens) == '你你好1a'
    assert all(.5 <= t['start'] < t['end'] <= .8 for t in tokens)
    assert all(a['end'] <= b['start'] for a, b in zip(tokens, tokens[1:]))
    assert report['chinese_speech_quality'] == 'NOT_VERIFIED'
    second = execute(source, tiny_model, tmp_path, output=tmp_path/'again.json', cache_dir=tmp_path/'cache')
    assert second['cache_hit'] is True and len(calls) == 1
    assert content_identity(source.path) == original_hash
    imported = import_alignment(tmp_path/'again.json', source,
                                parse_subtitle(source.subtitle_path, source.source_id))
    assert imported[0].alignment is None
    assert all(w.probability is None for w in imported[1].words)
    changed = execute(source, tiny_model, tmp_path, output=tmp_path/'different.json',
                      cache_dir=tmp_path/'cache', cue_indices=[0])
    assert not changed['cache_hit'] and changed['cache_key'] != report['cache_key']


@pytest.mark.parametrize('case', ['unknown', 'silence', 'overlap'])
def test_conservative_whole_cue_fallback(source, tiny_model, tmp_path, case):
    if case == 'unknown':
        path = Path(source.subtitle_path)
        path.write_text(path.read_text().replace('你你好1a', '你未知。'))
    elif case == 'overlap':
        path = Path(source.subtitle_path)
        path.write_text(path.read_text().replace('00:00:00,200', '00:00:00,600'))
    else:
        with wave.open(source.path, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b'\0\0' * 16000)
    source.fingerprint = content_identity(source.path)['sha256']
    source.subtitle_fingerprint = content_identity(source.subtitle_path)['sha256']
    report = execute(source, tiny_model, tmp_path)
    assert report['aligned_cues'] == 0
    result = json.loads((tmp_path/'alignment.json').read_text())
    assert all(t['status'] == 'missing' and t['start'] is None for t in result['cues'][0]['tokens'])


def test_pinned_model_and_input_changes_reject(source, tiny_model, tmp_path):
    pin = local.model_identity(tiny_model)
    (tiny_model/'LICENSE').write_text('self-created random fixture; not a trained model')
    with pytest.raises(ValueError, match='pin mismatch'):
        execute(source, tiny_model, tmp_path, model_sha256=pin)
    assert not (tmp_path/'alignment.json').exists()
    source.fingerprint = '0' * 64
    with pytest.raises(ValueError, match='identity mismatch'):
        execute(source, tiny_model, tmp_path)


@pytest.mark.parametrize('name', ['pytorch_model.bin', 'modeling_custom.py', 'adapter.safetensors'])
def test_unsafe_model_layout_rejected(source, tiny_model, tmp_path, name):
    (tiny_model/name).write_bytes(b'not executed')
    with pytest.raises(ValueError, match='unsupported'):
        execute(source, tiny_model, tmp_path)


def test_corrupt_cache_does_not_recompute(source, tiny_model, tmp_path, monkeypatch):
    execute(source, tiny_model, tmp_path, cache_dir=tmp_path/'cache')
    file = next((tmp_path/'cache').glob('*.json'))
    cache = json.loads(file.read_text()); cache['result']['cues'][0]['text'] = 'bad'
    file.write_text(json.dumps(cache))
    monkeypatch.setattr(local, '_load_model', lambda *args: pytest.fail('must not reload'))
    with pytest.raises(ValueError, match='Corrupt'):
        execute(source, tiny_model, tmp_path, output=tmp_path/'new.json', cache_dir=tmp_path/'cache')


def test_real_cli_produces_importable_evidence(source, tiny_model, tmp_path):
    manifest = tmp_path/'manifest.json'
    manifest.write_text(SourceManifest(sources=[source], config_fingerprint="fixture").model_dump_json())
    output = tmp_path/'cli.json'
    script = (
        "import runpy, socket; "
        "deny = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network denied')); "
        "socket.socket.connect = deny; socket.create_connection = deny; "
        "runpy.run_module('douyin_film_recap', run_name='__main__')"
    )
    env = {**os.environ, 'PYTHONPATH': str(Path(local.__file__).parents[1]),
           'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
           'HF_HUB_DISABLE_TELEMETRY': '1', 'OMP_NUM_THREADS': '1'}
    result = subprocess.run([sys.executable, '-c', script, 'run-local-alignment',
        '--manifest', str(manifest), '--source-id', source.source_id, '--cue-index', '1',
        '--model-dir', str(tiny_model), '--model-sha256', local.model_identity(tiny_model),
        '--output', str(output)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    validation = subprocess.run([sys.executable, '-c', script, 'validate-alignment',
        '--manifest', str(manifest), '--source-id', source.source_id, '--result', str(output)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert validation.returncode == 0, validation.stdout + validation.stderr



def test_model_content_change_invalidates_cache(source, tiny_model, tmp_path):
    first = execute(source, tiny_model, tmp_path, cache_dir=tmp_path/'cache')
    (tiny_model/'NOTICE').write_text('new content identity')
    second = execute(source, tiny_model, tmp_path, cache_dir=tmp_path/'cache', output=tmp_path/'second.json')
    assert not second['cache_hit'] and first['cache_key'] != second['cache_key']


def test_changed_input_during_forward_never_publishes(source, tiny_model, tmp_path, monkeypatch):
    original = local._audio_window
    def window(*args):
        audio = original(*args)
        Path(source.subtitle_path).write_text('changed')
        return audio
    monkeypatch.setattr(local, '_audio_window', window)
    with pytest.raises(local.SourceChangedDuringRead, match='changed'):
        execute(source, tiny_model, tmp_path, cache_dir=tmp_path/'cache')
    assert not (tmp_path/'alignment.json').exists() and not (tmp_path/'cache').exists()


def test_incomplete_weights_do_not_randomly_initialize(source, tiny_model, tmp_path):
    from safetensors.torch import load_file, save_file
    path = tiny_model/'model.safetensors'
    weights = load_file(path)
    weights.pop('lm_head.weight')
    save_file(weights, path, metadata={'format': 'pt'})
    with pytest.raises(ValueError, match='Incomplete'):
        execute(source, tiny_model, tmp_path)
    assert not (tmp_path/'alignment.json').exists()


def test_custom_config_is_rejected_before_model_load(source, tiny_model, tmp_path):
    path = tiny_model/'config.json'; config = json.loads(path.read_text())
    config['auto_map'] = {'AutoModel': 'evil.Model'}; path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='custom code'):
        execute(source, tiny_model, tmp_path)


def test_ctc_path_matches_bruteforce_score_for_small_cases():
    import itertools
    rng = np.random.default_rng(42)
    for labels in ([1, 1], [1, 2], [2]):
        probabilities = rng.dirichlet(np.ones(3), size=5)
        logs = np.log(probabilities)
        spans = local.ctc_spans(logs, list(labels), 0)
        # Exhaustively compute legal collapsed paths; returned nonblank cells must
        # be part of a globally optimal path, including the necessary repeated blank.
        winners = []
        best = -np.inf
        for path in itertools.product(range(3), repeat=5):
            collapsed = [v for i, v in enumerate(path) if v and (i == 0 or v != path[i-1])]
            if collapsed != list(labels):
                continue
            score = sum(logs[t, v] for t, v in enumerate(path))
            if score > best:
                best, winners = score, [path]
        reconstructed = [0] * 5
        for label, (start, end, _) in zip(labels, spans):
            reconstructed[start:end] = [label] * (end-start)
        assert tuple(reconstructed) in winners


@pytest.mark.parametrize('indices', [[], [1, 1], [-1], [5]])
def test_invalid_selection_never_publishes(source, tiny_model, tmp_path, indices):
    with pytest.raises(ValueError):
        execute(source, tiny_model, tmp_path, cue_indices=indices)
    assert not (tmp_path/'alignment.json').exists()


@pytest.mark.parametrize('field', ['media', 'subtitle'])
def test_input_bytes_invalidate_cache_when_manifest_is_updated(source, tiny_model, tmp_path, field):
    first = execute(source, tiny_model, tmp_path, cache_dir=tmp_path/'cache')
    if field == 'media':
        path = Path(source.path)
        data = bytearray(path.read_bytes()); data[-2:] = b'\0\0'; path.write_bytes(data)
        source.fingerprint = content_identity(path)['sha256']
    else:
        path = Path(source.subtitle_path)
        path.write_text(path.read_text().replace('你你好1a', '好你你1a'))
        source.subtitle_fingerprint = content_identity(path)['sha256']
    second = execute(source, tiny_model, tmp_path, output=tmp_path/'updated.json', cache_dir=tmp_path/'cache')
    assert not second['cache_hit'] and first['cache_key'] != second['cache_key']


def test_existing_output_is_never_overwritten(source, tiny_model, tmp_path):
    output = tmp_path/'alignment.json'; output.write_text('user-owned')
    with pytest.raises(FileExistsError):
        execute(source, tiny_model, tmp_path)
    assert output.read_text() == 'user-owned'


@pytest.mark.parametrize('suffix', ['ffconcat', 'mp4'])
def test_nested_local_media_rejected_regardless_of_extension(source, tiny_model, tmp_path, suffix):
    playlist = tmp_path/f'owned.{suffix}'
    playlist.write_text("ffconcat version 1.0\nfile 'owned-tone.wav'\n")
    source.path = str(playlist); source.filename = playlist.name
    source.fingerprint = content_identity(playlist)['sha256']
    with pytest.raises(subprocess.CalledProcessError) as exc:
        execute(source, tiny_model, tmp_path, cache_dir=tmp_path/'cache')
    assert b'not on whitelist' in exc.value.stderr
    assert not (tmp_path/'alignment.json').exists() and not (tmp_path/'cache').exists()


def test_extracted_waveform_comes_from_selected_sample_window(source, tmp_path):
    samples = np.concatenate([np.sin(np.arange(11025) / 22050 * 2 * np.pi * 220),
                              np.sin(np.arange(11025) / 22050 * 2 * np.pi * 880)])
    with wave.open(source.path, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(22050)
        wav.writeframes((samples * 12000).astype('<i2').tobytes())
    waveform = local._audio_window(local.shutil.which('ffmpeg'), Path(source.path), .5, .3)
    assert len(waveform) == 4800
    spectrum = abs(np.fft.rfft(waveform))
    peak = np.fft.rfftfreq(len(waveform), 1 / 16000)[np.argmax(spectrum)]
    assert peak == pytest.approx(880, abs=4)


def test_self_contained_mp4_audio_remains_supported(source, tiny_model, tmp_path):
    media = tmp_path/'self-contained.mp4'
    subprocess.run([local.shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-i', source.path,
                    '-c:a', 'aac', str(media)], capture_output=True, check=True, timeout=30)
    source.path = str(media); source.filename = media.name
    source.fingerprint = content_identity(media)['sha256']
    report = execute(source, tiny_model, tmp_path)
    assert report['aligned_cues'] == 1

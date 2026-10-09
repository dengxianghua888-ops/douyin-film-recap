"""Real encode/readback regressions for source identity and wrapper propagation."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
import editing_runtime as runtime
import source_binding


@pytest.fixture
def tools():
    ffmpeg = os.environ.get('EDITING_FFMPEG') or shutil.which('ffmpeg')
    ffprobe = os.environ.get('EDITING_FFPROBE') or shutil.which('ffprobe')
    assert ffmpeg and ffprobe, 'Set EDITING_FFMPEG/EDITING_FFPROBE; media regressions must not be skipped.'
    return runtime.Tools(ffmpeg, ffprobe)


@pytest.fixture
def media(tmp_path, tools):
    result = {}
    for color in ('red', 'blue'):
        path = tmp_path / (color + '.mp4')
        subprocess.run([tools.ffmpeg, '-nostdin', '-v', 'error', '-n', '-f', 'lavfi',
                        '-i', 'color=c=' + color + ':s=64x64:r=25:d=0.4',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=0.4',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(path)], check=True)
        result[color] = path
    return result


def plan(path, *, speed='1', mute=False, duplicate=False):
    clip = {'id': 'one', 'source_id': 'main', 'start': 0, 'end': 0.4,
            'gain_db': 0, 'speed': speed, 'mute': mute}
    return {'schema': 'execution-plan/1', 'fps': '25', 'width': 64, 'height': 64, 'fit': 'contain',
            'sources': {'main': {'path': str(path), 'sha256': runtime.sha256(path)}},
            'clips': [clip, {**clip, 'id': 'two'}] if duplicate else [clip],
            'allow_source_reuse': duplicate}


def mode(kind):
    return {'schema': 'source-consumption/1', 'mode': kind}


def rgb(path, tools):
    raw = subprocess.run([tools.ffmpeg, '-v', 'error', '-i', str(path), '-frames:v', '1',
                          '-vf', 'scale=1:1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         check=True, stdout=subprocess.PIPE).stdout
    return tuple(raw[:3])


def inject_during_encode(monkeypatch, original, replacement, *, restore=False, snapshot=False):
    owned = runtime.owned_process
    calls = []

    def consume(command, timeout=300, cwd=None):
        if '-filter_complex' in command and str(command[-1]).endswith('preview.mp4'):
            victim = original
            if snapshot:
                victim = next(Path(x) for x in command if 'source-snapshots/source-' in str(x))
                victim.chmod(0o600)
            before = victim.read_bytes()
            victim.write_bytes(replacement.read_bytes())
            calls.append(str(victim))
            try:
                return owned(command, timeout=timeout, cwd=cwd)
            finally:
                if restore:
                    victim.write_bytes(before)
        return owned(command, timeout=timeout, cwd=cwd)

    monkeypatch.setattr(runtime, 'owned_process', consume)
    return calls


@pytest.mark.parametrize('kind', ['boundary', 'snapshot'])
def test_replacement_during_real_encoding_fails(kind, tmp_path, media, tools, monkeypatch):
    request = {'operation': 'timeline-render', 'plan': plan(media['red']), 'source_consumption': mode(kind)}
    calls = inject_during_encode(monkeypatch, media['red'], media['blue'])
    folder = tmp_path / 'failed'
    receipt = runtime.run(request, folder, tools)
    assert calls and receipt['status'] == 'FAILED'
    assert 'SOURCE_IDENTITY_CHANGED' in receipt['error']
    binding = json.loads((folder / 'source-binding.json').read_text())
    assert binding['adoptable'] is False and binding['status'] == 'FAILED'
    assert 'result' not in receipt
    pixel = rgb(folder / 'preview.mp4', tools)
    assert (pixel[0] > 200) if kind == 'snapshot' else (pixel[2] > 200)


@pytest.mark.parametrize('kind,channel', [('boundary', 2), ('snapshot', 0)])
def test_aba_guarantee_is_explicit_and_snapshot_consumes_bound_color(kind, channel, tmp_path, media, tools, monkeypatch):
    selected_plan = plan(media['red'])
    calls = inject_during_encode(monkeypatch, media['red'], media['blue'], restore=True)
    folder = tmp_path / kind
    receipt = runtime.run({'operation': 'timeline-render', 'plan': selected_plan,
                           'source_consumption': mode(kind)}, folder, tools)
    assert calls and receipt['status'] == 'SUCCEEDED', receipt.get('error')
    assert rgb(folder / 'preview.mp4', tools)[channel] > 200
    normalized = json.loads((folder / 'normalized-plan.json').read_text())
    assert normalized['request_plan_sha256'] == runtime.fingerprint(selected_plan)
    assert normalized['sources']['main']['path'] == str(media['red'])
    binding = json.loads((folder / 'source-binding.json').read_text())
    assert binding['sources'][0]['sha256'] == selected_plan['sources']['main']['sha256']
    if kind == 'snapshot':
        snapshot = Path(binding['sources'][0]['execution_path'])
        assert snapshot.stat().st_ino != media['red'].stat().st_ino
        assert normalized['sources']['main']['media']['format']['filename'] == str(snapshot)
    else:
        assert 'A-to-B-to-A' in binding['protection']


def test_snapshot_itself_changed_is_rejected(tmp_path, media, tools, monkeypatch):
    calls = inject_during_encode(monkeypatch, media['red'], media['blue'], snapshot=True)
    receipt = runtime.run({'operation': 'timeline-render', 'plan': plan(media['red']),
                           'source_consumption': mode('snapshot')}, tmp_path / 'tampered', tools)
    assert calls and receipt['status'] == 'FAILED'
    assert 'SOURCE_SNAPSHOT_IDENTITY_CHANGED' in receipt['error']


@pytest.mark.parametrize('speed,mute,duplicate', [('1', False, False), ('0.5', False, False),
                                                 ('0.5', True, False), ('1', False, True)])
def test_stable_default_identity_atempo_mute_and_repeated_sources(speed, mute, duplicate, tmp_path, media, tools):
    request = {'operation': 'timeline-render', 'plan': plan(media['red'], speed=speed, mute=mute, duplicate=duplicate)}
    if speed != '1' and not mute:
        request['audio_backend'] = {'kind': 'ffmpeg-atempo'}
    folder = tmp_path / 'stable'
    receipt = runtime.run(request, folder, tools)
    assert receipt['status'] == 'SUCCEEDED', receipt.get('error')
    assert receipt['result']['source_consumption']['selection']['mode'] == 'boundary'
    assert len(json.loads((folder / 'source-binding.json').read_text())['sources']) == 1


@pytest.mark.parametrize('failure', ['space', 'timeout', 'cancel'])
def test_snapshot_preparation_fails_without_media_execution(failure, tmp_path, media, tools, monkeypatch):
    original = runtime.sha256(media['red'])
    if failure == 'space':
        monkeypatch.setattr(source_binding.shutil, 'disk_usage', lambda path: type('Usage', (), {'free': 0})())
    elif failure == 'timeout':
        monkeypatch.setattr(source_binding.SourceBinding, 'deadline', lambda self: -1)
    else:
        digest = source_binding.stable_digest

        def cancel(path, deadline):
            if str(path).endswith('.partial'):
                raise KeyboardInterrupt
            return digest(path, deadline)

        monkeypatch.setattr(source_binding, 'stable_digest', cancel)
    folder = tmp_path / 'prep'
    receipt = runtime.run({'operation': 'timeline-render', 'plan': plan(media['red']),
                           'source_consumption': mode('snapshot')}, folder, tools)
    assert receipt['status'] == 'FAILED'
    assert not (folder / 'preview.mp4').exists()
    assert not list(folder.rglob('*.partial'))
    assert runtime.sha256(media['red']) == original
    assert json.loads((folder / 'source-binding.json').read_text())['adoptable'] is False
    if failure == 'cancel':
        assert receipt['cancelled'] is True


def work(tmp_path, source, tools):
    document = {'schema': 'work-document/1', 'plan': plan(source), 'captions': {}, 'caption_style': None,
                'audio_tracks': {}, 'style_bindings': {}, 'notes': {}}
    store = tmp_path / 'work.sqlite'
    result = runtime.run({'operation': 'work-version', 'action': 'init', 'store': str(store), 'work_id': 'regression',
                          'document': document, 'message': 'synthetic', 'author': 'agent'}, tmp_path / 'init', tools)
    assert result['status'] == 'SUCCEEDED', result.get('error')
    return store, result['result'], document


def test_work_and_batch_propagate_snapshot_and_verify_resume(tmp_path, media, tools):
    store, state, document = work(tmp_path, media['red'], tools)
    spec = {'store': str(store), 'expected_version': state['version'], 'source_consumption': mode('snapshot')}
    current = runtime.run({'operation': 'work-render', **spec}, tmp_path / 'current', tools)
    assert current['status'] == 'SUCCEEDED', current.get('error')
    actual = current['result']['source_consumption']
    assert actual['selection']['mode'] == 'snapshot' and actual['adoptable']
    assert current['result']['document_sha256'] == runtime.fingerprint(document)
    child = json.loads((tmp_path / 'current/timeline/receipt.json').read_text())
    assert child['result']['source_consumption']['selection'] == actual['selection']
    batch = tmp_path / 'batch'
    prepared = runtime.run({'operation': 'work-batch-render', 'action': 'prepare', 'batch_dir': str(batch),
                            'batch_id': 'synthetic', 'jobs': [{'id': 'one', **spec}]}, tmp_path / 'prepare', tools)
    assert prepared['status'] == 'SUCCEEDED', prepared.get('error')
    request = {'operation': 'work-batch-render', 'action': 'run', 'batch_dir': str(batch),
               'manifest_sha256': prepared['result']['manifest_sha256'], 'job_ids': ['one'], 'retry_failed': False}
    rendered = runtime.run(request, tmp_path / 'batch-run', tools)
    assert rendered['status'] == 'SUCCEEDED', rendered.get('error')
    assert rendered['result']['jobs'][0]['status'] == 'RENDERED'
    resumed = runtime.run(request, tmp_path / 'batch-resume', tools)
    assert resumed['status'] == 'SUCCEEDED', resumed.get('error')
    assert resumed['result']['events'][0]['action'] == 'REUSED_VERIFIED'
    media['red'].write_bytes(media['blue'].read_bytes())
    stale = runtime.run(request, tmp_path / 'batch-stale', tools)
    assert stale['status'] == 'SUCCEEDED', stale.get('error')
    assert stale['result']['jobs'][0]['status'] == 'INVALID_OUTPUT'


def test_work_failed_child_cannot_publish_binding(tmp_path, media, tools, monkeypatch):
    store, state, _ = work(tmp_path, media['red'], tools)
    inject_during_encode(monkeypatch, media['red'], media['blue'])
    folder = tmp_path / 'work-fail'
    receipt = runtime.run({'operation': 'work-render', 'store': str(store), 'expected_version': state['version'],
                           'source_consumption': mode('snapshot')}, folder, tools)
    assert receipt['status'] == 'FAILED'
    assert not (folder / 'render-binding.json').exists()
    assert json.loads((folder / 'source-binding.json').read_text())['adoptable'] is False


def test_unknown_explicit_mode_does_not_fallback(tmp_path, media, tools):
    request = {'operation': 'timeline-render', 'plan': plan(media['red']),
               'source_consumption': mode('unsupported')}
    receipt = runtime.run(request, tmp_path / 'unsupported', tools)
    assert receipt['status'] == 'FAILED'
    assert 'SOURCE_CONSUMPTION_MODE_UNSUPPORTED' in receipt['error']


def test_no_audio_snapshot(tmp_path, media, tools):
    silent = tmp_path / 'silent.mp4'
    tools.ff(['-i', str(media['red']), '-an', '-c:v', 'copy', str(silent)])
    receipt = runtime.run({'operation': 'timeline-render', 'plan': plan(silent),
                           'source_consumption': mode('snapshot')}, tmp_path / 'silent-run', tools)
    assert receipt['status'] == 'SUCCEEDED', receipt.get('error')
    assert receipt['result']['source_consumption']['adoptable']


def test_candidate_preview_propagates_mode_without_committing(tmp_path, media, tools):
    store, state, document = work(tmp_path, media['red'], tools)
    candidate = copy.deepcopy(document)
    candidate['notes']['review'] = 'synthetic preview'
    scope = {field: [] for field in ['clip_ids', 'source_ids', 'caption_ids', 'audio_ids',
                                   'style_keys', 'output_fields', 'freeze_positions']}
    scope.update(note_keys=['review'], caption_style=False, freeze_duration=True)
    proposed = runtime.run({'operation': 'timeline-revise', 'base_version': state['version'],
                            'document': document, 'expected_document_sha256': runtime.fingerprint(document),
                            'candidate': candidate, 'scope': scope}, tmp_path / 'candidate', tools)
    assert proposed['status'] == 'SUCCEEDED', proposed.get('error')
    candidate_path = tmp_path / 'candidate/candidate.json'
    receipt = runtime.run({'operation': 'work-render', 'store': str(store), 'expected_version': state['version'],
                           'preview_candidate': {'path': str(candidate_path), 'sha256': runtime.sha256(candidate_path)},
                           'source_consumption': mode('snapshot')}, tmp_path / 'preview-candidate', tools)
    assert receipt['status'] == 'SUCCEEDED', receipt.get('error')
    assert receipt['result']['source_consumption']['selection']['mode'] == 'snapshot'
    assert receipt['result']['adoption_authorized_by_preview'] is False
    from batch_ops import work_state
    assert work_state(str(store))['document_sha256'] == runtime.fingerprint(document)


def test_work_additional_audio_source_is_bound_through_mix(tmp_path, media, tools, monkeypatch):
    document = {'schema': 'work-document/1', 'plan': plan(media['red']), 'captions': {}, 'caption_style': None,
                'audio_tracks': {'music': {'source': {'path': str(media['blue']), 'sha256': runtime.sha256(media['blue'])},
                                         'start': 0, 'end': 0.4, 'anchor_clip_id': None, 'offset': 0, 'gain_db': -6}},
                'style_bindings': {}, 'notes': {}}
    store = tmp_path / 'with-audio.sqlite'
    initialized = runtime.run({'operation': 'work-version', 'action': 'init', 'store': str(store), 'work_id': 'audio',
                               'document': document, 'message': 'synthetic', 'author': 'agent'}, tmp_path / 'init-audio', tools)
    assert initialized['status'] == 'SUCCEEDED', initialized.get('error')
    owned = runtime.owned_process
    consumed = []

    def mutate(command, timeout=300, cwd=None):
        if str(command[-1]).endswith('mixed.mp4'):
            media['blue'].write_bytes(media['red'].read_bytes())
            consumed.extend(x for x in command if 'source-snapshots' in str(x))
        return owned(command, timeout=timeout, cwd=cwd)

    monkeypatch.setattr(runtime, 'owned_process', mutate)
    folder = tmp_path / 'mixed-failure'
    receipt = runtime.run({'operation': 'work-render', 'store': str(store),
                           'expected_version': initialized['result']['version'],
                           'source_consumption': mode('snapshot')}, folder, tools)
    assert consumed and receipt['status'] == 'FAILED'
    assert 'SOURCE_IDENTITY_CHANGED' in receipt['error']
    assert not (folder / 'render-binding.json').exists()


def test_original_changes_while_copying_is_rejected(tmp_path, media, tools, monkeypatch):
    request = {'operation': 'timeline-render', 'plan': plan(media['red']), 'source_consumption': mode('snapshot')}
    original_open = Path.open
    opens = []

    class ChangingReader:
        def __init__(self, stream):
            self.stream = stream
            self.changed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            chunk = self.stream.read(size)
            if not self.changed:
                self.changed = True
                media['red'].write_bytes(media['blue'].read_bytes())
            return chunk

    def opening(path, *args, **kwargs):
        result = original_open(path, *args, **kwargs)
        if path == media['red'] and args and args[0] == 'rb':
            opens.append(path)
            if len(opens) == 2:  # Initial hash then the actual copy reader.
                return ChangingReader(result)
        return result

    monkeypatch.setattr(Path, 'open', opening)
    folder = tmp_path / 'copy-race'
    receipt = runtime.run(request, folder, tools)
    assert receipt['status'] == 'FAILED'
    assert 'SOURCE_CHANGED_DURING_COPY' in receipt['error']
    assert not (folder / 'preview.mp4').exists()
    assert not list(folder.rglob('*.partial'))


def test_replaced_snapshot_path_is_rejected_even_with_same_content(tmp_path, media, tools):
    class ReplacingTools(runtime.Tools):
        def probe(self, path):
            if 'source-snapshots' in str(path) and not hasattr(self, 'replaced'):
                self.replaced = True
                path = Path(path)
                path.parent.chmod(0o700)
                replacement = path.with_suffix('.replacement')
                replacement.write_bytes(path.read_bytes())
                os.replace(replacement, path)
                path.parent.chmod(0o500)
            return super().probe(path)

    altered_tools = ReplacingTools(tools.ffmpeg, tools.ffprobe)
    receipt = runtime.run({'operation': 'timeline-render', 'plan': plan(media['red']),
                           'source_consumption': mode('snapshot')}, tmp_path / 'replaced-copy', altered_tools)
    assert receipt['status'] == 'FAILED'
    assert 'SOURCE_SNAPSHOT_FILE_CHANGED' in receipt['error']

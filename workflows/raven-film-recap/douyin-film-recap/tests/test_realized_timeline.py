from types import SimpleNamespace

import pytest

from douyin_film_recap.render_contracts import RenderContractError, rational
from douyin_film_recap.render_timeline import build_realized_timeline


def setup_segments(expected=0.101, count=20):
    segments = [SimpleNamespace(segment_id=str(i), mode='voiceover',
        audio_duration_sec=expected, tts_word_boundaries=[]) for i in range(count)]
    contracts = {s.segment_id: dict(frame_count=3, fps='30', sample_count=4800,
        sample_rate=48000, decoded_sample_count=4800, padding=0, encoder_delay=0,
        padding_policy='decoded-minus-packet-end/1') for s in segments}
    return SimpleNamespace(segments=segments), contracts


def test_many_fractional_segments_use_measured_frame_grid():
    board, contracts = setup_segments()
    timeline = build_realized_timeline(board, 30, contracts)
    assert timeline[-1]['end_frame'] == 60
    assert rational(timeline[-1]['end']) == 2
    assert all(a['end'] == b['start'] for a, b in zip(timeline, timeline[1:]))


def test_small_per_segment_drift_cannot_accumulate_silently():
    board, contracts = setup_segments(expected=0.11)
    with pytest.raises(RenderContractError, match='REALIZED_CUMULATIVE_DRIFT'):
        build_realized_timeline(board, 30, contracts)

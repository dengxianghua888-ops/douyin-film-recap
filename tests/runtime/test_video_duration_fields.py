"""Only measured integer frame durations qualify, across FFmpeg field names."""
from fractions import Fraction
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
import editing_runtime as runtime


@pytest.mark.parametrize('fields,accepted', [
    ({'pkt_duration': 1}, True), ({'duration': 1}, True),
    ({'duration': 1, 'pkt_duration': 1}, True),
    ({}, False), ({'duration': 0}, False), ({'duration': -1}, False),
    ({'duration': '1'}, False), ({'duration': True}, False),
    ({'duration': 1, 'pkt_duration': 2}, False),
])
def test_frame_duration_evidence(monkeypatch, fields, accepted):
    frame = dict(media_type='video', stream_index=0, best_effort_timestamp=0, **fields)
    monkeypatch.setattr(runtime, 'exec_tool', lambda *a, **k: SimpleNamespace(stdout=json.dumps({'frames': [frame]})))
    tools = runtime.Tools()
    monkeypatch.setattr(tools, 'binary', lambda _: 'unused')
    media = {'streams': [{'codec_type': 'video', 'index': 0, 'time_base': '1/25', 'avg_frame_rate': '25/1'}]}
    if accepted:
        result = tools.selected_video_clock('unused', media, Fraction(0), Fraction(1, 25))
        assert result['observed_intervals'] == [['0', '1/25']]
    else:
        with pytest.raises(runtime.ContractError, match='SOURCE_VIDEO_FRAME_DURATION'):
            tools.selected_video_clock('unused', media, Fraction(0), Fraction(1, 25))

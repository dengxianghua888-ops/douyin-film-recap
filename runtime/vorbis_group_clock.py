"""Bounded Matroska/Vorbis EBML-lace playback hypothesis, never source evidence.

Complete block sample counts constrain a common sub-tick origin. Existence of
that origin is ordinary playback compatibility, not proof against sub-tick
physical gaps. Unknown containers, structures and partial groups retain observed
coverage. No decoder, media process, or source modification is performed here.
"""
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path

POLICY = 'vorbis-complete-ebml-blocks/common-phase-1'
MAX_HEADER_BYTES = 4096
MAX_BLOCK_BYTES = 64 * 1024 * 1024


class UnsupportedGroup(ValueError):
    pass


def check(condition, reason):
    if not condition:
        raise UnsupportedGroup(reason)


def supported(format_name, codec_name, time_base):
    try:
        return (codec_name == 'vorbis' and
                bool({'matroska', 'webm'} & set(str(format_name).split(','))) and
                Fraction(time_base) == Fraction(1, 1000))
    except (TypeError, ValueError, ZeroDivisionError):
        return False


def _vint(data, offset):
    check(0 <= offset < len(data) and data[offset] != 0, 'BLOCK_VINT_UNAVAILABLE')
    width = next(n for n in range(1, 9) if data[offset] & (1 << (8-n)))
    check(offset + width <= len(data), 'BLOCK_HEADER_TRUNCATED')
    number = data[offset] & ((1 << (8-width))-1)
    for byte in data[offset+1:offset+width]:
        number = (number << 8) | byte
    return number, width


def parse_block_header(prefix, *, data_position, prefix_position, file_size):
    """Parse one actual SimpleBlock EBML-lace header from a bounded byte prefix.

    data_position is ffprobe's pos. The actual A3 + EBML size must terminate
    exactly there; bytes that merely resemble a block elsewhere are not used.
    This helper does not claim to validate the whole container hierarchy.
    """
    check(type(data_position) is int and type(prefix_position) is int and
          0 <= prefix_position < data_position < file_size and
          isinstance(prefix, bytes) and len(prefix) <= MAX_HEADER_BYTES,
          'BLOCK_POSITION_UNAVAILABLE')
    offset = data_position-prefix_position
    check(0 < offset <= 9 and offset < len(prefix), 'BLOCK_ELEMENT_HEADER_UNAVAILABLE')
    candidates = []
    for i in range(max(0, offset-9), offset):
        if prefix[i] != 0xa3:
            continue
        try:
            size, width = _vint(prefix, i+1)
        except UnsupportedGroup:
            continue
        if i+1+width == offset and size != (1 << (7*width))-1:
            candidates.append((i, size))
    if len(candidates) > 1:
        candidates = [(i, size) for i, size in candidates
                      if 0 < size <= MAX_BLOCK_BYTES and data_position+size <= file_size]
    check(len(candidates) == 1, 'BLOCK_ELEMENT_HEADER_UNAVAILABLE')
    element_offset, size = candidates[0]
    check(0 < size <= MAX_BLOCK_BYTES and data_position+size <= file_size,
          'BLOCK_LENGTH_UNSUPPORTED')
    body = prefix[offset:]
    track, width = _vint(body, 0)
    check(track > 0 and width+3 <= len(body), 'BLOCK_TRACK_UNAVAILABLE')
    relative = int.from_bytes(body[width:width+2], 'big', signed=True)
    flags = body[width+2]
    lacing = (flags >> 1) & 3
    check(lacing in (0, 1, 3), 'BLOCK_LACING_UNSUPPORTED')
    cursor = width+3
    if lacing == 0:
        count = 1
        sizes = [size-cursor]
        structure = 'SIMPLEBLOCK_NO_LACING'
    else:
        check(cursor < len(body), 'BLOCK_HEADER_TRUNCATED')
        count = body[cursor]+1
        cursor += 1
        check(2 <= count <= 256, 'BLOCK_LACE_COUNT_UNSUPPORTED')
        sizes = []
        if lacing == 1:
            structure = 'SIMPLEBLOCK_XIPH_LACING'
            for _ in range(count-1):
                total = 0
                while True:
                    check(cursor < len(body), 'BLOCK_HEADER_TRUNCATED')
                    byte = body[cursor]
                    cursor += 1
                    total += byte
                    if byte != 255:
                        break
                sizes.append(total)
        else:
            structure = 'SIMPLEBLOCK_EBML_LACING'
            first, width = _vint(body, cursor)
            cursor += width
            sizes = [first]
            for _ in range(count-2):
                encoded, width = _vint(body, cursor)
                cursor += width
                sizes.append(sizes[-1]+encoded-((1 << (7*width-1))-1))
        sizes.append(size-cursor-sum(sizes))
    check(all(x > 0 for x in sizes) and cursor <= size, 'BLOCK_LACE_SIZE_INVALID')
    return {'position': data_position, 'element_position': prefix_position+element_offset,
            'track_number': track, 'relative_timecode_ticks': relative,
            'lace_count': count, 'lace_sizes': sizes, 'block_data_size': size,
            'header_size': cursor, 'structure': structure,
            'header_sha256': hashlib.sha256(prefix[element_offset:offset+cursor]).hexdigest()}


def read_block_headers(path, positions):
    """Only bounded reads of the same local source; failure never grants coverage."""
    result = {}
    positions = list(dict.fromkeys(str(x) for x in positions))
    if len(positions) > 50000:
        return {}, {'scope': 'BLOCK_COUNT_UNSUPPORTED'}
    errors = {}
    try:
        path = Path(path)
        before = path.stat()
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        with path.open('rb') as stream:
            for raw_position in positions:
                try:
                    position = int(raw_position)
                    check(str(position) == str(raw_position) and position >= 1,
                          'BLOCK_POSITION_UNAVAILABLE')
                    start = max(0, position-9)
                    stream.seek(start)
                    prefix = stream.read(MAX_HEADER_BYTES)
                    result[str(position)] = parse_block_header(
                        prefix, data_position=position, prefix_position=start,
                        file_size=before.st_size)
                except (ValueError, TypeError, OSError) as exc:
                    errors[str(raw_position)] = str(exc)
        if signature(before) != signature(path.stat()):
            return {}, {'scope': 'SOURCE_CHANGED_DURING_BLOCK_READ'}
    except OSError as exc:
        return {}, {'scope': 'BLOCK_READ_UNAVAILABLE: '+str(exc)}
    return result, errors


def _merge(ranges):
    merged = []
    for a, b in sorted((Fraction(a), Fraction(b)) for a, b in ranges):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [[str(a), str(b)] for a, b in merged]


def merge_window_playback(windows, observed_intervals):
    """Reapply one phase constraint across runs sharing identical complete blocks.

    Only adjacency already proved inside a complete run supplies graph edges.
    Interval overlap, window endpoints and numerical file-position proximity never
    supply an edge or a missing block. A repeated block contributes samples once.
    Conflicting observations quarantine that block locally, not the whole source.
    """
    rate = windows[0]['sample_rate']
    tick = Fraction(windows[0]['time_base'])
    basis = {'policy': POLICY, 'ordinary_only': True,
             'meaning': 'quantized playback hypothesis; not proof of physically gapless samples',
             'absolute_phase_convention': 'nearest half-open tick cell; muxer convention unverified',
             'sub_tick_physical_gaps': 'NOT_DISTINGUISHABLE_FROM_QUANTIZATION',
             'window_bases': [c.get('playback_basis', {'status': 'OBSERVED_ONLY'}) for c in windows],
             'aggregation': 'identical complete block overlap joins proved adjacency; deduplicated common-phase constraints',
             'complete_groups': [], 'rejected_groups': [], 'runs': [], 'components': []}
    barriers = list({json.dumps(b, sort_keys=True): b for c in windows
                     for b in c.get('playback_barriers', [])}.values())
    catalog, occurrences, edges, invalid, eligible = {}, {}, set(), set(), set()
    declared_identities = {}

    def normalized_group(rec, anchor):
        pos = str(rec['position'])
        counts = rec['sample_counts']
        check(pos.isdecimal() and int(pos) > 0 and pos == str(int(pos)) and isinstance(counts, list) and counts and
              all(type(n) is int and n > 0 for n in counts) and
              type(rec['samples']) is int and sum(counts) == rec['samples'],
              'CROSS_WINDOW_GROUP_SAMPLES_INCONSISTENT')
        anchor = Fraction(anchor)
        check(anchor >= 0 and isinstance(rec['header_sha256'], str) and rec['header_sha256'],
              'CROSS_WINDOW_GROUP_IDENTITY_UNAVAILABLE')
        check('anchor_seconds' not in rec or Fraction(rec['anchor_seconds']) == anchor,
              'CROSS_WINDOW_GROUP_ANCHOR_INCONSISTENT')
        return {'position': pos, 'anchor': anchor, 'samples': rec['samples'],
                'sample_counts': list(counts), 'duration': Fraction(rec['samples'], rate),
                'header_sha256': rec['header_sha256'], 'track_number': rec.get('track_number')}

    def register(g):
        pos = g['position']
        occurrences.setdefault(pos, []).append(g)
        if pos in catalog and catalog[pos] != g:
            invalid.add(pos)
        else:
            catalog[pos] = g

    for wi, clock in enumerate(windows):
        wb = clock.get('playback_basis', {})
        if wb.get('policy') != POLICY:
            continue  # Unsupported/legacy selectors grant only observed coverage.
        local = {}
        for record in wb.get('complete_groups', []):
            pos = str(record.get('position'))
            identity = {key: record.get(key) for key in
                        ('samples', 'sample_counts', 'header_sha256', 'track_number')}
            if pos in declared_identities and declared_identities[pos] != identity:
                invalid.add(pos)
            declared_identities[pos] = identity
            if pos in local and record != local[pos]:
                invalid.add(pos)
            local[pos] = record
            # New selectors record anchors on every complete group, including
            # groups omitted from a playback run. Their contradictions count too;
            # membership alone never grants a reconstructed range.
            if 'anchor_seconds' in record:
                try:
                    register(normalized_group(record, record['anchor_seconds']))
                except (UnsupportedGroup, KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
                    invalid.add(pos)
                    basis['rejected_groups'].append({'window': wi, 'position': pos, 'reason': str(exc)})
        for run in wb.get('runs', []):
            positions, anchors = run.get('positions', []), run.get('actual_anchor_seconds', [])
            try:
                check(len(positions) == len(anchors) > 0 and
                      all(str(p).isdecimal() for p in positions) and
                      all(int(a) < int(b) for a, b in zip(positions, positions[1:])),
                      'CROSS_WINDOW_RUN_IDENTITY_UNAVAILABLE')
            except (UnsupportedGroup, ValueError, TypeError) as exc:
                basis['rejected_groups'].append({'window': wi, 'positions': positions, 'reason': str(exc)})
                continue
            normalized = []
            for raw_pos, anchor in zip(positions, anchors):
                pos = str(raw_pos)
                try:
                    g = normalized_group(local[pos], anchor)
                    register(g)
                    eligible.add(pos)
                    normalized.append(g)
                except (UnsupportedGroup, KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
                    invalid.add(pos)
                    normalized.append(None)  # Never join across a missing group.
                    basis['rejected_groups'].append({'window': wi, 'position': pos, 'reason': str(exc)})
            if all(g is not None for g in normalized) and sum(g['samples'] for g in normalized) != run.get('decoded_samples'):
                basis['rejected_groups'].append({'window': wi, 'positions': positions,
                                                'reason': 'CROSS_WINDOW_RUN_SAMPLES_INCONSISTENT'})
                continue  # Valid groups remain usable singly, not as a claimed run.
            edges.update((a['position'], b['position']) for a, b in zip(normalized, normalized[1:])
                         if a is not None and b is not None)

    # Do not let a contradictory duplicate be hidden by a later valid window.
    # Its own possible extent is quarantined; unrelated prefix/suffix survive.
    for pos in sorted(invalid, key=lambda p: int(p) if p.isdecimal() else -1):
        gs = occurrences.get(pos, [])
        for left, right in sorted({(g['anchor']-tick/2, g['anchor']+g['duration']+tick/2) for g in gs}):
            # Different claimed anchors quarantine their individual extents,
            # not the entire time span between them and unrelated valid audio.
            barriers.append({'interval': [str(max(Fraction(0), left)), str(right)],
                             'position': pos, 'reason': 'CROSS_WINDOW_GROUP_IDENTITY_CONFLICT'})
        basis['rejected_groups'].append({'position': pos, 'reason': 'CROSS_WINDOW_GROUP_IDENTITY_CONFLICT'})
    catalog = {p:g for p,g in catalog.items() if p in eligible and p not in invalid}
    edges = {(a,b) for a,b in edges if a in catalog and b in catalog}
    successors, predecessors = {}, {}
    for a,b in edges:
        successors.setdefault(a, set()).add(b)
        predecessors.setdefault(b, set()).add(a)
    rejected_edges = {(a,b) for a,b in edges
                      if len(successors[a]) > 1 or len(predecessors[b]) > 1}
    for a,b in sorted(rejected_edges, key=lambda x: (int(x[0]), int(x[1]))):
        left, right = catalog[a]['anchor']+catalog[a]['duration'], catalog[b]['anchor']
        barriers.append({'interval': [str(min(left, right)), str(max(left, right))],
                         'left_position': a, 'right_position': b,
                         'reason': 'CROSS_WINDOW_ADJACENCY_CONFLICT'})
    edges -= rejected_edges
    successor = dict(edges)
    predecessor = {b:a for a,b in edges}
    groups = []
    for pos in sorted(catalog, key=int):
        if pos in predecessor:
            continue
        component = []
        while pos is not None:
            component.append(pos)
            groups.append(catalog[pos])
            pos = successor.get(pos)
        groups.append(None)
        basis['components'].append({'positions': component,
                                    'decoded_samples': sum(catalog[p]['samples'] for p in component)})
    basis['complete_groups'] = [
        {'position': p, 'anchor_seconds': str(g['anchor']), 'samples': g['samples'],
         'sample_counts': g['sample_counts'], 'header_sha256': g['header_sha256'],
         'track_number': g['track_number']} for p,g in sorted(catalog.items(), key=lambda x:int(x[0]))]
    return _reconstruct_groups(groups, tick, observed_intervals, basis, barriers)


def playback_clock(observed_intervals, observation, blocks, *, stream_index,
                   sample_rate, time_base, codec_name, format_name):
    """Pure function. blocks must come from actual source header reads.

    A block is eligible only with exactly one matching decoded frame per declared
    lace, including sizes, positions, stream, DTS/PTS and duration. Each complete
    run shares one half-open quantization-phase interval of width one time-base
    tick. Nearest and floor quantization differ by a common origin translation;
    existence alone cannot prove which muxer convention or real sub-tick timing
    occurred. The representative origin and uncertainty are recorded explicitly.
    """
    basis = {'policy': POLICY, 'ordinary_only': True,
             'meaning': 'quantized playback hypothesis; not proof of physically gapless samples',
             'absolute_phase_convention': 'nearest half-open tick cell; muxer convention unverified',
             'sub_tick_physical_gaps': 'NOT_DISTINGUISHABLE_FROM_QUANTIZATION',
             'complete_groups': [], 'rejected_groups': [], 'runs': []}
    output = {'playback_intervals': [list(x) for x in observed_intervals],
              'playback_barriers': [], 'playback_basis': basis}
    if not supported(format_name, codec_name, time_base):
        basis['fallback'] = 'UNSUPPORTED_CONTAINER_CODEC_OR_TIME_BASE'
        return output
    try:
        check(type(sample_rate) is int and sample_rate > 0 and type(stream_index) is int,
              'SELECTED_RATE_OR_STREAM_UNAVAILABLE')
        tick = Fraction(time_base)
        check(isinstance(observation, dict) and isinstance(observation.get('packets_and_frames'), list),
              'PACKETS_AND_FRAMES_UNAVAILABLE')
        rows = observation['packets_and_frames']
        check(len(rows) <= 100000, 'PACKET_FRAME_OBSERVATION_LIMIT')
        packets, frames = [], []
        for row in rows:
            check(isinstance(row, dict) and row.get('type') in ('packet', 'frame'),
                  'PACKET_FRAME_STRUCTURE_UNAVAILABLE')
            check(type(row.get('stream_index')) is int and row.get('stream_index') == stream_index,
                  'GROUP_STREAM_MISMATCH')
            check('sample_rate' not in row or str(row['sample_rate']) == str(sample_rate),
                  'GROUP_RATE_MISMATCH')
            (packets if row['type'] == 'packet' else frames).append(row)
        # Every frame must remain associated with an observed packet position.
        positions = []
        packet_groups, frame_groups = {}, {}
        for p in packets:
            pos = str(p.get('pos'))
            check(pos.isdecimal() and int(pos) > 0, 'PACKET_POSITION_UNAVAILABLE')
            if not positions or pos != positions[-1]:
                check(pos not in packet_groups, 'INTERLEAVED_OR_REPEATED_BLOCK_POSITION')
                positions.append(pos)
            packet_groups.setdefault(pos, []).append(p)
        check(all(int(a) < int(b) for a, b in zip(positions, positions[1:])),
              'NONMONOTONE_BLOCK_POSITION')
        check(all(str(f.get('pkt_pos')) in packet_groups for f in frames), 'FRAME_POSITION_MISMATCH')
        for f in frames:
            frame_groups.setdefault(str(f.get('pkt_pos')), []).append(f)
        groups = []
        tracks = set()
        for pos in positions:
            ps = packet_groups[pos]
            fs = frame_groups.get(pos, [])
            try:
                proof = blocks.get(pos)
                check(isinstance(proof, dict) and proof.get('structure') in ('SIMPLEBLOCK_EBML_LACING', 'SIMPLEBLOCK_XIPH_LACING', 'SIMPLEBLOCK_NO_LACING') and
                      proof.get('position') == int(pos), 'BLOCK_HEADER_UNAVAILABLE')
                check(len(ps) == len(fs) == proof['lace_count'] == len(proof['lace_sizes']),
                      'INCOMPLETE_OR_DUPLICATE_PACKET_FRAME_GROUP')
                check([int(p['size']) for p in ps] == proof['lace_sizes'], 'LACE_PACKET_SIZE_MISMATCH')
                check(all(type(p.get('pts')) is int and type(p.get('dts')) is int and
                          type(p.get('duration')) is int and p['duration'] > 0 and
                          p.get('codec_type') == 'audio' and p['pts'] == p['dts'] for p in ps),
                      'PACKET_CLOCK_UNAVAILABLE')
                packet_keys = [(p['pts'], p['dts'], str(p['size']), p['duration']) for p in ps]
                check(len(set(packet_keys)) == len(packet_keys), 'DUPLICATE_PACKET')
                frame_keys = []
                sample_by_key = {}
                for f in fs:
                    check(f.get('media_type') == 'audio' and type(f.get('nb_samples')) is int and
                          f['nb_samples'] > 0 and type(f.get('best_effort_timestamp')) is int and
                          type(f.get('pkt_dts')) is int and type(f.get('pkt_duration')) is int,
                          'FRAME_CLOCK_UNAVAILABLE')
                    key = (f['best_effort_timestamp'], f['pkt_dts'], str(f.get('pkt_size')), f['pkt_duration'])
                    frame_keys.append(key)
                    sample_by_key[key] = f['nb_samples']
                check(Counter(packet_keys) == Counter(frame_keys), 'PACKET_FRAME_NOT_BIJECTIVE')
                check(all(b['pts'] == a['pts']+a['duration'] for a, b in zip(ps, ps[1:])),
                      'INTERNAL_PACKET_CLOCK_UNEXPLAINED')
                samples = [sample_by_key[k] for k in packet_keys]
                # Reject unexplained packet-duration estimates, including a
                # metadata duration larger than the decoded sample duration.
                check(all(Fraction(p['duration']) == Fraction(n, sample_rate)//tick
                          for p, n in zip(ps, samples)), 'PACKET_DURATION_NOT_SAMPLE_FLOOR')
                tracks.add(proof['track_number'])
                g = {'position': pos, 'anchor': ps[0]['pts']*tick,
                     'samples': sum(samples), 'sample_counts': samples,
                     'duration': Fraction(sum(samples), sample_rate),
                     'proof': proof}
                groups.append(g)
                basis['complete_groups'].append({'position': pos, 'samples': g['samples'],
                    'sample_counts': samples, 'header_sha256': proof['header_sha256'],
                    'anchor_seconds': str(g['anchor']), 'track_number': proof['track_number']})
            except (UnsupportedGroup, KeyError, TypeError, ValueError) as exc:
                groups.append(None)
                basis['rejected_groups'].append({'position': pos, 'reason': str(exc)})
        check(len(tracks) <= 1, 'BLOCK_TRACK_CHANGED')
    except (UnsupportedGroup, KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        basis['fallback'] = str(exc)
        basis['complete_groups'] = []
        return output

    return _reconstruct_groups(groups, tick, observed_intervals, basis)


def _reconstruct_groups(groups, tick, observed_intervals, basis, barriers=()):
    output = {'playback_basis': basis}
    additions = []
    barriers = list(barriers)
    run = []
    low = high = elapsed = None

    def finish():
        if not run:
            return
        # Zero keeps the first observed block anchor when feasible. Otherwise
        # select the interior midpoint; never call this sample-precise evidence.
        phase = Fraction(0) if low <= 0 < high else (low+high)/2
        start = run[0]['anchor']+phase
        end = start+sum((g['duration'] for g in run), Fraction(0))
        if start < 0:
            basis['rejected_groups'].append({'positions': [g['position'] for g in run],
                                            'reason': 'NEGATIVE_RECONSTRUCTED_ORIGIN'})
            return
        additions.append([start, end])
        basis['runs'].append({'positions': [g['position'] for g in run],
            'common_phase_seconds_half_open': [str(low), str(high)],
            'representative_phase_seconds': str(phase),
            'playback_interval': [str(start), str(end)],
            'decoded_samples': sum(g['samples'] for g in run),
            'actual_anchor_seconds': [str(g['anchor']) for g in run]})
        return start, end

    for g in groups+[None]:
        if g is None:
            finish()
            run = []
            continue
        if not run:
            run = [g]
            low, high, elapsed = -tick/2, tick/2, g['duration']
            continue
        residual = g['anchor']-run[0]['anchor']-elapsed
        next_low, next_high = max(low, residual-tick/2), min(high, residual+tick/2)
        if next_low >= next_high:
            # Preserve the compatible prefix, but a new origin must never make
            # a crossing request appear continuous after interval union. Keep an
            # explicit barrier, including negative/zero-width phase conflicts.
            previous = finish()
            previous_end = previous[1] if previous is not None else run[-1]['anchor']+run[-1]['duration']
            barrier = {'interval': [str(min(previous_end, g['anchor'])), str(max(previous_end, g['anchor']))],
                'left_position': run[-1]['position'], 'right_position': g['position'],
                'reason': 'GROUP_ANCHORS_HAVE_NO_COMMON_PHASE',
                'previous_phase': [str(low), str(high)], 'next_residual': str(residual)}
            barriers.append(barrier)
            basis['rejected_groups'].append(barrier)
            run = [g]
            low, high, elapsed = -tick/2, tick/2, g['duration']
            continue
        run.append(g)
        low, high, elapsed = next_low, next_high, elapsed+g['duration']
    ranges = [[Fraction(a), Fraction(b)] for a, b in _merge(list(observed_intervals)+additions)]
    # Also cut barriers out of the returned ranges. Consumers must still check
    # playback_barriers: overlap aggregation could otherwise rejoin a zero-width
    # barrier, or another window could obscure an incompatible phase observation.
    for barrier in barriers:
        left, right = map(Fraction, barrier['interval'])
        cut = []
        for a, b in ranges:
            if b <= left or a >= right:
                cut.append([a, b])
            else:
                if a < left: cut.append([a, left])
                if right < b: cut.append([right, b])
        ranges = cut
    output['playback_intervals'] = [[str(a), str(b)] for a, b in ranges]
    output['playback_barriers'] = barriers
    basis['status'] = 'PLAYBACK_GROUP_QUANTIZED_UNCERTAIN' if additions else 'OBSERVED_ONLY'
    return output

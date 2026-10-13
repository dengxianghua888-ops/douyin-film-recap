# Official OTIO parser acceptance

## Dependency and permission scope

The film `dev` extra pins **opentimelineio==0.18.1**. It is not a runtime
requirement and the exporter/CLI does not import it. The existing GitHub CI film
job already installs `.[dev]` on Python 3.12 before running tests; no workflow or
deployment change is needed. No local install is attempted in the restricted
cloud environment, and there is no alternative download/install route around its
access restrictions.

Public upstream evidence checked 2026-10-13:

- [Official v0.18.1 release](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/releases/tag/v0.18.1)
- [PyPI 0.18.1 metadata and release files](https://pypi.org/project/OpenTimelineIO/0.18.1/): release November 9, 2025; Python >3.9.0; CPython 3.12 Linux x86-64 wheel available
- [Pinned upstream setup.py](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/v0.18.1/setup.py): package version, Python support and empty runtime install_requires
- [Apache-2.0 license](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/v0.18.1/LICENSE.txt) and [NOTICE](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/v0.18.1/NOTICE.txt)
- [Official native adapter documentation](https://opentimelineio.readthedocs.io/en/v0.18.1/tutorials/adapters.html): the core distribution includes the native JSON adapter; external NLE adapters are separate
- [Official time-range API documentation](https://opentimelineio.readthedocs.io/en/v0.18.1/tutorials/time-ranges.html)

Observed target CI wheel:

- Filename: `opentimelineio-0.18.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl`
- Published SHA-256: `8f0924f818b496cf771612d489082bdb83f42b6bd97ed06589dd2e2c086742c9`

The checksum is a provenance record for that specific wheel, not a claim that
pyproject's version pin enforces archive hashes on every platform. Tests also
assert the actually installed distribution version. CI obtains the upstream
distribution using its existing package installation. No upstream source, binary,
media fixture or adapter implementation is copied into this repository. Its
Apache license and NOTICE remain applicable to that distribution; any future
binary redistribution must preserve the required notices. This does not make
claims about film/voice/model/media rights or license an NLE integration.

## Acceptance fixtures

`tests/test_otio_official_parser.py` is mandatory in a full dev install: it uses
a normal import, not `importorskip`. The five tests cover:

1. Installed version exactly 0.18.1 and dependency confined to the dev extra.
2. Official parser reading an X1 package made from newly generated FFmpeg color
   clips and sine/WAV audio; two sources, repeated occurrence, explicit audio
   gaps, stable IDs, media SHA references and cross-cut Chinese subtitle sidecar.
3. Official read → write → read preserving source/target ranges, track kind,
   media references and occurrence IDs, then saved-snapshot X2 readback without
   adopting anything. The upstream Clip.1 → Clip.2 upgrade is explicitly checked.
4. 30000/1001 fps at exact 30-frame windows, plus independently represented
   48048-sample audio windows. Original fractions remain in sidecars; no invented
   decimal precision or re-quantization.
5. A source-window edit made through the official object API surviving write and
   saved readback under the same occurrence identity, with an exact field diff.

Comparison uses the official objects' source ranges, duration and parent ranges;
it does not merely compare two JSON dictionaries produced by our serializer.
The official parser does not decode or render media. The synthetic media fixture
also exercises X1's existing independent ffprobe scan, not NLE rendering.

Upstream serialization may add optional fields unknown to X2. Their raw bytes
remain opaque, and an affected edit can conservatively require review rather
than being automatically accepted. The tests do not disable that guard to create
an apparently successful roundtrip.

## Evidence boundary

Adding these tests is not a passing result. Parser acceptance is established only
by an actual successful test/CI run for the matching commit. A failed or missing
parser installation is a failed/incomplete dev test environment, not a skip or a
PASS. The restricted local environment cannot run these five tests; its syntax
check and existing dependency-free tests remain separate evidence.

Even after a successful parser test run, actual Kdenlive/other-host import,
metadata survival after host saved reopen, audio routing, rendered equivalence,
and adopted roundtrip remain NOT_RUN. Runtime-generated packages continue to
report their own official parser status as NOT_RUN, since their exporter does
not call it; testing representative fixtures does not certify every export.

In an existing permitted dev environment:

```bash
python -m pytest -q tests/test_otio_official_parser.py
```

## Recorded acceptance: 2026-10-13

The official-parser suite was actually executed in
[CI run 38378974343](https://github.com/dengxianghua888-ops/douyin-film-recap/actions/runs/38378974343)
for commit `f317db6d2d2915bd96457174a639c595bf3f1750`. All three jobs succeeded.
The film job `115234351324` logged installation of `opentimelineio-0.18.1` from
the CPython 3.12 manylinux x86-64 wheel.

The downloaded
[film JUnit artifact 11802880930](https://github.com/dengxianghua888-ops/douyin-film-recap/actions/runs/38378974343/artifacts/11802880930)
contains **401 tests, zero failures, zero errors and zero skips**. Each of the
five `OfficialOTIOParserTests` named above is present with no failure/error/skip
record. Artifact ZIP SHA-256:
`c13cc3feea824ce93bc887787a1aba7a879631feda9da757486e8934a833523b`.

This establishes native-parser fixture acceptance for that commit and version.
It does not establish an actual NLE import/reopen/render, adopted roundtrip, or
per-export parser validation; those boundaries above are unchanged.

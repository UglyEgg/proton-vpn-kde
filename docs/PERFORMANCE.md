# Performance

## Interpretation

PSS and SwapPss account for shared and swapped memory; RSS is labeled separately.
Results are bounded measurements of identified builds/fixtures, not guaranteed
product budgets. The current Fastest branch has no new whole-client performance
qualification.

## Fastest retry selection

Same-host Core 5.8.11 model/selection probe with 18,221 synthetic logicals,
149 countries, and 201 location groups; three warm untraced runs per case,
with separate allocation runs. Socket construction is prohibited. Before/after
medians isolate selection, not whole-client latency or memory.

| Selection work | Before | Current |
| --- | ---: | ---: |
| Eligible preferred, global | 272.789 ms | 0.032 ms |
| Eligible preferred, location group | 391.300 ms | 0.054 ms |
| Group with no feature match | 346.450 ms | 4.587 ms |
| Preferred check + group alternative query | 811.249 ms | 5.333 ms |

The last row retains the original two-call probe; production now enumerates
alternatives once per switching tick. Preferred group selection's traced peak
falls from 1,604,168 to 5,259 bytes. The preferred-plus-alternative pair peaks
at 18,155 bytes after the correction.

Preferred checks use Core's ID index and single-object eligibility/grouping.
Alternative projection includes only the selected country, uses current Core
objects, and does not sort the cached catalog. Global alternative ranking is
still linear in the eligible catalog; no parallel Core access or persistent
secondary index is introduced. Unit work-bound checks and actual-Core fixtures
guard the selection scope independently of these timing samples.

## Whole-client observations

| Sample | PSS + SwapPss | Conditions |
| --- | ---: | --- |
| Agent + backend, Core 5.8.3 | 128.3 MiB median | Mature connected 0.14.3 runtime, window closed; seven samples |
| Agent + backend, Core 5.8.11 | About 169.1 MiB | Connected after guarded recovery; seven samples |
| Open Control Center, Core 5.8.11 | 65.2 MiB separately | Same post-recovery observation |

Different servers and process lifecycles prevent an A/B interpretation.
Descriptor/thread counts were stable across the seven 5.8.11 samples
(agent 16/4, backend 32/23). These observations do not establish a steady-state
Core regression or long-run retention bound.

The resident agent does not load QML, server/application models, authentication
transport, or Core. Backend idle retirement and page lifetime are specified in
[Architecture](ARCHITECTURE.md), not inferred from these samples.

## Inspector probe

A two-cycle 0.14.5 release-preparation offscreen probe on 2026-10-21 measured:

| State | PSS (KiB) | Private memory (KiB) |
| --- | ---: | ---: |
| Initial Overview | 69,443 | 58,724 |
| First close | 73,175 | 62,456 |
| Second close | 73,563 | 62,844 |

The first close retained 3,732 KiB; the second added 388 KiB. This measures the
Control Center against the isolated demo backend, not resident Core memory or
an A/B improvement. Two cycles expose warm-up retention, not a leak-free
plateau. Software rendering excludes native GPU-driver retention; long-duration
qualification remains open.

## Search fixture

Actual Core 5.7.0 cache/model types with a fake authenticated session;
initialization, login, and socket creation are prohibited. The fixture has
18,220 logical servers, 201 projected locations, and a 26,030,781-byte cache.
Python 3.14; 50 iterations/query.

| Setup metric | Result |
| --- | ---: |
| Cache load | 237.377 ms |
| Projection + first query | 114.539 ms |
| Retained / peak traced allocation | 2,640,777 / 5,289,966 bytes |

| Query | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| `ch` | 1.243 ms | 1.435 ms | 1.524 ms |
| `zur` | 0.766 ms | 1.053 ms | 1.357 ms |
| `us-` | 0.407 ms | 0.431 ms | 0.498 ms |
| `#1` | 0.232 ms | 0.242 ms | 0.358 ms |
| `a` | 6.186 ms | 6.887 ms | 7.270 ms |
| no match | 0.299 ms | 0.570 ms | 1.711 ms |

This is a search-fixture baseline, not current-Core or network-latency evidence.

## Server-string sharing

Signed vendor Core 5.8.3 versus its string-sharing overlay; identical real
18,220-server cache, seven fresh processes/variant.

| Metric, median | Vendor | Shared strings |
| --- | ---: | ---: |
| Loaded process PSS | 85,380 KiB | 62,596 KiB |
| Retained traced allocation | 38,660,402 bytes | 29,474,344 bytes |
| Peak traced allocation | 59,782,316 bytes | 50,700,881 bytes |
| Load time | 360.1 ms | 425.7 ms |

PSS falls 26.7%; decode time rises 18.2%. These are component results, not
whole-client RSS. The sharing pool retains one object per equal string rather
than one per server.

## Supported-overlay comparison

Same-host 5.8.3/5.8.11 overlays with sharing, measured 2026-10-15. Seven normal
and seven separate tracemalloc runs/variant; sockets are prohibited. Frozen
18,221-server cache: 25,977,530 bytes, SHA-256
`996fd95d4b3fba44d09c637c10954f9b8463794387aee9db76ba5aff1ff9fc69`.

| Metric, median | 5.8.3 | 5.8.11 |
| --- | ---: | ---: |
| Loaded PSS + SwapPss | 69,865 KiB | 70,315 KiB |
| Peak RSS, normal runs | 102,092 KiB | 128,056 KiB |
| Load + model construction | 195.374 ms | 197.417 ms |
| Retained traced allocation | 38,177,747 bytes | 38,178,105 bytes |
| Peak traced allocation | 61,088,762 bytes | 86,934,181 bytes |

Retained allocation differs by 358 bytes. Peak RSS rises 25.4 MiB and traced
peak 24.6 MiB, consistent with retaining the raw buffer while parsing decoded
JSON. No additional cache-buffer optimization is included. Traced runs are
excluded from process-PSS/timing rows.

## Reproduce

```bash
PYTHONPATH=backend /usr/bin/python3 scripts/benchmark-search.py --iterations 50
scripts/measure-demo-memory.sh build
scripts/measure-inspector-retention.sh build
```

The scripts own isolated state and cleanup. Reports contain aggregate counts,
timing, and allocations, not account data. Allocator, Qt/KDE, platform plugin,
GPU, and page-cache differences affect results.

Open measurements: controlled current-stack whole-client A/B, long-duration
resident/Inspector/diagnostic retention, live GPU behavior, cold navigation,
and representative cache scaling.

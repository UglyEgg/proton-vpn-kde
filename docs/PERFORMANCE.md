# Performance

## Runtime measurements

Measurements are proportional set size (PSS) unless noted. They are regression
evidence for the stated build and fixture, not fixed product requirements.

| State | Result | Scope |
| --- | ---: | --- |
| Resident agent, disconnected | 11,124 KiB PSS | Fedora 44 Plasma session; no Control Center or backend |
| Resident agent, isolated offscreen | 29,440 KiB RSS | Qt offscreen session |
| Agent + backend, connected for 10 minutes | 130.8–133.8 MiB PSS + SwapPss | 21 samples from 0.13 development build `58b3d83`; Control Center closed |
| Connected resident CPU | 0.537 CPU-seconds / 10 minutes | 0.089% of one core over the same interval |
| Complete disconnected demo stack | 76.5 MiB combined PSS | Published 0.11.3; backend, agent, and Control Center |
| Complete disconnected demo stack | 80.8 MiB median combined PSS | Accepted 0.12 mechanics baseline; three runs |
| 0.14.1 vs 0.13.1 base | 95,074 vs 95,002 KiB combined PSS | Same-host isolated A/B; +72 KiB (+0.08%) |

During the connected retention sample, agent private writable memory plus swap
remained 7,800 KiB; backend private writable memory plus swap fell from 114,660
to 113,408 KiB. Thread and descriptor counts were constant. This is bounded
observation, not proof that every reconnect or longer session is leak-free.

The resident agent does not load QML, server/application models, authentication
transport, or Proton Core. It observes without a backend lease and acquires one
only for an explicit action. A disconnected, unleased backend retires through a
one-shot deadline; active tunnels and capture recovery are event-owned without a
polling loop.

The same release-source/base A/B measured Control Center RSS at +448 KiB and
startup CPU at +0.03 seconds. These are small same-host differences, not a
cross-version product budget. Package-manager readiness inspection is lazy and
runs only when Local setup is opened.

## Inspector retention

Two 20-cycle, same-process Inspector open/close probes retained 7,284 KiB of
private writable memory after warm-up. The final five closes varied by 128 KiB,
and owned-page/window-descendant counts returned to baseline after every close.
An explicit diagnostic GC after ten seconds reclaimed a further 1,024 KiB.

A two-cycle 0.14.3 offscreen probe on 2026-10-15 produced:

| State | PSS (KiB) | Private memory (KiB) |
| --- | ---: | ---: |
| Initial Overview | 84,600 | 76,068 |
| First close | 92,525 | 87,044 |
| Second close | 93,557 | 88,076 |

The short probe shows warm-up retention and a smaller second increment; two
cycles do not establish long-run behavior. Offscreen software rendering excludes
native GPU-driver retention.

## Search benchmark

The corrected offline benchmark uses actual Core 5.7.0 cache/model types and an
explicit fake authenticated session. It prohibits initialization, login, and
socket creation. Production authentication and search code are unchanged.

Fixture: 26,030,781-byte cache, 18,220 logical servers, 201 projected
locations, system Python 3.14, 50 iterations per query.

| Metric | Result |
| --- | ---: |
| Cache load | 237.377 ms |
| Projection build + first query | 114.539 ms |
| Retained traced allocation | 2,640,777 bytes |
| Peak traced allocation | 5,289,966 bytes |

| Query | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| `ch` | 1.243 ms | 1.435 ms | 1.524 ms |
| `zur` | 0.766 ms | 1.053 ms | 1.357 ms |
| `us-` | 0.407 ms | 0.431 ms | 0.498 ms |
| `#1` | 0.232 ms | 0.242 ms | 0.358 ms |
| `a` | 6.186 ms | 6.887 ms | 7.270 ms |
| no match | 0.299 ms | 0.570 ms | 1.711 ms |

The projection stores immutable scalar search fields, not Proton server
objects. It resolves load, maintenance, and account availability from current
Core objects for matched records. Load-only refreshes do not rebuild it;
topology or localized-name changes invalidate it for lazy reconstruction.

The earlier direct-object implementation measured 418–968 ms for representative
queries against a comparable 18,138-server cache. The scalar projection measured
0.2–5.7 ms and returned identical fields and ordering for 12 representative
queries. Host/cache differences preclude interpreting that comparison as a
universal ratio.

## Core server-string sharing

The Fedora 5.8.3 overlay was measured against the unmodified signed 5.8.3
payload with the same real 18,220-server cache. Seven isolated processes were
used for each variant.

| Metric | Vendor 5.8.3 | String sharing | Difference |
| --- | ---: | ---: | ---: |
| Server-list load PSS, median | 85,380 KiB | 62,596 KiB | -22,784 KiB (-26.7%) |
| Retained traced allocation | 38,660,402 bytes | 29,474,344 bytes | -9,186,058 bytes |
| Peak traced allocation | 59,782,316 bytes | 50,700,881 bytes | -9,081,435 bytes |
| Load time, median | 360.1 ms | 425.7 ms | +65.6 ms (+18.2%) |

Without sharing, the loaded model retained 18,220 distinct objects for each of
149 country and 195 city values. The patched model retained one object per
equal value. This is a server-list component A/B, not whole-client RSS, and it
exposes a one-time decode-time tradeoff rather than claiming a free reduction.

An independent installed-package check used a sanitized 18,000-server fixture
and seven fresh processes per variant. Median PSS fell from 93,442 to 61,006
KiB (-34.7%); retained traced allocation fell from 42,508,970 to 27,740,013
bytes. Median load time rose from 323.3 to 413.6 ms (+27.9%). This corroborates
the real-cache result while preserving the same component-only and one-time
load-cost qualifications.

## Core 5.8.11 beta comparison (2026-10-15)

Same-host, alternating fresh-process comparison of the 5.8.3 and 5.8.11
overlays. Both retain string sharing. One frozen public server cache contains
18,221 logical servers (25,977,530 bytes; SHA-256
`996fd95d4b3fba44d09c637c10954f9b8463794387aee9db76ba5aff1ff9fc69`).
Each variant has seven normal runs and seven separate tracemalloc runs.
Network socket creation is prohibited; no session or live API is initialized.

| Metric, median | Overlay 5.8.3 | Overlay 5.8.11 |
| --- | ---: | ---: |
| Loaded process PSS + SwapPss | 69,865 KiB | 70,315 KiB |
| Process peak RSS, normal runs | 102,092 KiB | 128,056 KiB |
| Cache load + model construction, normal runs | 195.374 ms | 197.417 ms |
| Retained traced allocations | 38,177,747 bytes | 38,178,105 bytes |
| Peak traced allocations | 61,088,762 bytes | 86,934,181 bytes |

The retained allocation difference is 358 bytes; both models share 149 country
strings across 18,221 servers. The new cache implementation raises process peak
RSS by 25.4 MiB and traced peak by 24.6 MiB. Its raw byte buffer remains live
while decoded JSON text is parsed, consistent with the extra peak allocation.
This is a component regression, not evidence of increased steady-state
whole-client memory. Traced runs are excluded from the process-PSS/timing rows.
No extra cache-buffer optimization is included in this candidate.

Before installation, seven samples of the mature connected 0.14.3 agent/backend
on Core 5.8.3 measured 131,371 KiB median combined PSS + SwapPss (128.3 MiB),
with the window closed. After guarded recovery on Core 5.8.11, seven read-only
connected samples measured about 169.1 MiB for the agent/backend; the open
window separately measured 65.2 MiB. Agent/backend file descriptors and
threads stayed at 16/32 and 4/23 across those samples. The observations use
different connection lifecycles and servers, so they do not establish a
5.8.11 steady-state regression. A controlled whole-client comparison and
long-duration retention test remain open.

## Reproduce

```bash
PYTHONPATH=backend /usr/bin/python3 scripts/benchmark-search.py --iterations 50
scripts/measure-demo-memory.sh build
scripts/measure-inspector-retention.sh build
```

All scripts use isolated state and remove their processes and files. The search
report prints only cache size, aggregate counts, timing, allocation, and result
counts. PSS varies with allocators, Qt/KDE versions, platform plugins, and page
cache.

Measurement gaps: live GPU rendering, cold navigation latency, representative
cache scaling, normal-GC long-duration Inspector/diagnostics retention, and a
long-duration 0.14.3/Core-5.8.3 resident-state matrix.

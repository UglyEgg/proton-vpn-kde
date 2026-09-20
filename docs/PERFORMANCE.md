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

A shorter frozen-source probe produced:

| State | PSS (KiB) | Private memory (KiB) |
| --- | ---: | ---: |
| Initial Overview | 64,780 | 59,348 |
| First close | 67,524 | 62,092 |
| Second close | 68,574 | 63,120 |

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
long-duration 0.14.1/Core-5.7 resident-state matrix.

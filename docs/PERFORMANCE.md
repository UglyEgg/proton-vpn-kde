# Performance

## Resident Plasma agent

The system tray, global shortcuts, notifications, favorites, and auto-connect
run in `proton-vpn-kde-agent`. The agent does not
load QML, server or application models, the protected authentication transport,
or Proton's Python core. It observes without a resident client lease and uses
one only transiently while an explicit connection action is starting.

On the Fedora 44 Plasma development session, the disconnected agent settled at
58,412 KiB RSS and 11,124 KiB proportional set size; systemd attributed about
8.1 MiB to its private cgroup footprint. The same binary on an isolated
offscreen Qt session settled at 29,440 KiB RSS. In both cases no Control Center
or Python backend remained running, and NetworkManager stayed disconnected.
The live figure includes the real Plasma platform theme, status notifier,
global-shortcut, and notification integrations.

The lifecycle regressions start the agent beside a demo backend with a
two-second idle grace period. The backend exits while the observing agent
remains alive, while a temporary explicit-action lease is acquired and released
around commands. Separate startup tests prove that a live frontend protects a
provider prompt and a vanished frontend releases it. The resident process
therefore does not retain the substantially larger Python server model while
disconnected.

Backend lifetime is event-driven. Lease acquisition performs one D-Bus owner
check, and the authenticated `NameOwnerChanged` stream releases a vanished
frontend. Connected, busy, and packet-capture states wait for Core or client
events without a repeating timer; only an exit-eligible idle backend arms its
one-shot grace deadline.

The Connection Inspector adds no resident process or backend collector. Its
QML page is created only when selected in the already-running Control Center,
uses the controller's existing bounded connection snapshot, and loads its
cold settings models only when first opened. Explicit refreshes are coalesced
while one snapshot request is in flight and reload all three Inspector-owned
settings models. A static UI gate rejects timers and worker or socket collectors
in that page.

A later alternating same-host differential compared the exact event-driven
baseline (`75ffc5e`) with the pre-remediation 0.12.0 candidate (`98969fc`). The
median combined PSS moved from 91,828 KiB to 92,956 KiB: an increase of 1,128
KiB, or 1.23%, almost entirely in the Control Center. Unstripped artifacts grew
by 405,696 bytes while executable text and data grew by roughly 44 KiB. This
supersedes the earlier three-run observation that classified the difference as
sharing variance; the smaller positive result is still bounded and consistent
with adding the dormant page and controller fields.

The measured 0.12.0 baseline adds a repeatable same-process retention probe.
It measures the Control Center at Overview, after opening and destroying the Inspector,
then repeats that open/destroy cycle in the same process. The probe reports both
PSS and private resident memory because PSS can change when another process
starts or stops sharing the same Qt pages. Three runs retained 580, 580, and
576 KiB of private memory after the first close, which is normal one-time QML
and allocator warming. The second close changed private memory by -60, -76,
and -56 KiB from the first-close sample. The exact accepted runtime revision
`d2e7a74` repeated the 576 KiB first-cycle and -60 KiB second-cycle results. No
per-open retained growth was observed. The earlier corresponding second-cycle
PSS changes were -109, -168, and -57 KiB; the exact revision measured -60 KiB.
These figures do not claim that allocator caches return to the cold baseline;
they demonstrate that repeated use does not accumulate another page-sized
allocation.

## Search performance

The native global-search benchmark uses Proton's existing local server cache.
It does not contact Proton, connect a VPN, or read credentials.

## Before-and-after search measurement

The measured cache was 24,328,124 bytes and contained 18,138 logical servers
across 200 locations. Measurements used system Python 3.14 and Proton VPN API
Core 5.6.10. The original implementation was sampled five times per query; the
generation-scoped projection was sampled 50 times per query.

| Query | Result shape | Original median | Projection median | Improvement |
| --- | --- | ---: | ---: | ---: |
| `zur` | one location | 418.049 ms | 0.715 ms | 585x |
| `us-` | 100 servers | 968.139 ms | 0.387 ms | 2,501x |
| `#1` | 100 servers | 601.205 ms | 0.209 ms | 2,876x |
| `a` | 100 locations and 100 servers | 420.881 ms | 5.213 ms | 81x |
| no match | no results | 421.318 ms | 0.233 ms | 1,808x |

Building the projection and completing its first query took 114.053 ms. Its
traced steady allocation was 2,625,623 bytes, with a 5,267,488-byte peak while
building. This is a bounded memory trade for eliminating repeated normalization,
sorting, and physical-server expansion on every keystroke.

The projection stores only immutable scalar search fields. It retains no
official Proton server or server-list object, never reorders Proton's list, and
resolves current load, maintenance, and plan availability through the current
official objects only for matched records. Load-only refreshes therefore remain
live without rebuilding. A full topology refresh or localized-location-name
refresh invalidates the projection and rebuilds it lazily on the next search.

An exact comparison with the previous implementation produced identical result
fields and ordering for 12 representative location, exact-server, feature,
broad, punctuation, and no-match queries.

## Measured unreleased 0.12.0 baseline

Three isolated disconnected/demo runs of the measured runtime revision
`d2e7a74` measured 83,114, 82,629, and 82,754 KiB combined PSS, for a median of
82,754 KiB (80.8 MiB). The median components were 21,570 KiB for the Python
backend, 5,542 KiB for the resident agent, and 55,599 KiB for the Control
Center. This is 2.5 MiB above the earlier absolute pre-final median but remains
within the cross-run page-sharing variation demonstrated by the stronger
alternating comparison above; no runtime implementation changed between those
measurements. These absolute figures do not replace that differential result.

## Current 0.11.3 release measurement

The 0.11.3 release battery repeated the measurements after the Protun reconnect
and stale-backend-state recovery work. An isolated offscreen demo stack settled
at:

| Process | PSS | RSS |
| --- | ---: | ---: |
| Python backend | 22,041 KiB | 34,364 KiB |
| Resident Plasma agent | 4,833 KiB | 32,588 KiB |
| Control Center | 51,492 KiB | 112,324 KiB |
| **Combined** | **78,366 KiB (76.5 MiB)** | Not additive for shared pages |

This is below the 81.2 MiB 0.11.2 release result, the earlier 86.0 MiB
post-remediation result, and the 90.6 MiB pre-remediation source result. It is
an isolated disconnected/demo measurement, not a claim about a live connected
Core session.

The current cache was 24,342,666 bytes, with 18,138 logical servers and 200
locations. Projection construction plus its first query took 116.743 ms. The
projection retained 2,629,679 bytes of traced allocation and peaked at
5,267,584 bytes while building.

| Query | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| `ch` | 1.217 ms | 1.511 ms | 2.228 ms |
| `zur` | 0.749 ms | 1.143 ms | 2.856 ms |
| `us-` | 0.409 ms | 0.696 ms | 0.891 ms |
| `#1` | 0.205 ms | 0.229 ms | 0.308 ms |
| `a` | 5.667 ms | 6.418 ms | 6.931 ms |
| no match | 0.273 ms | 0.487 ms | 1.189 ms |

Each row used 50 iterations against the existing local cache. A separate
visual-startup timing attempt was discarded because the isolated session lacked
portal and systemd services and backend activation interfered with the sample;
no startup-latency claim is made from that run.

## Reproduce

With an existing Proton server cache:

```bash
PYTHONPATH=backend /usr/bin/python3 scripts/benchmark-search.py --iterations 50
```

The report includes only cache size, aggregate counts, timing, allocation, and
result counts. It does not print server names, cache contents, or account data.

Measure the disconnected demo processes from an existing build:

```bash
scripts/measure-demo-memory.sh build
```

Measure same-process Inspector retention with two consecutive open/close
cycles:

```bash
scripts/measure-inspector-retention.sh build
```

Both scripts use an isolated session bus, temporary configuration, the
deterministic backend, and an offscreen Qt platform. The demo-stack script also
starts the resident agent and samples all three processes after a five-second
settling period. The retention probe runs the Control Center without the agent
and reads both PSS and private memory from `/proc/self/smaps_rollup`; private
memory is the primary same-process retention signal because it is not
re-apportioned as page-sharing peers change. Both scripts remove their isolated
processes and state. PSS varies with the allocator, Qt/KDE package versions,
and the host page cache; it is a regression measurement rather than a fixed
product requirement.

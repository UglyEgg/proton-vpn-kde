# Performance

## Resident Plasma agent

Version `0.9.0` moves the system tray, global shortcuts, notifications,
favorites, and auto-connect into `proton-vpn-kde-agent`. The agent does not
load QML, server or application models, the protected authentication transport,
or Proton's Python core. It also observes the backend without registering a
client lease.

On the Fedora 44 Plasma development session, the disconnected agent settled at
57,960 KiB RSS. The same binary on an isolated offscreen Qt session settled at
29,440 KiB RSS. In both cases no Control Center or Python backend remained
running, and NetworkManager stayed disconnected. The live figure includes the
real Plasma platform theme, status notifier, global-shortcut, and notification
integrations.

The lifecycle regression starts the agent beside a demo backend with a
two-second idle grace period. The backend exits while the agent remains alive,
proving that the resident process does not retain the substantially larger
Python server model while disconnected.

## Search performance

Phase 5 profiles the native global search against Proton's existing local
server cache. The benchmark does not contact Proton, connect a VPN, or read
credentials.

## Fedora 44 measurement

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

## Reproduce

With an existing Proton server cache:

```bash
PYTHONPATH=backend /usr/bin/python3 scripts/benchmark-search.py --iterations 50
```

The report includes only cache size, aggregate counts, timing, allocation, and
result counts. It does not print server names, cache contents, or account data.

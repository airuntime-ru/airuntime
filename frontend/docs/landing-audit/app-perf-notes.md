# App UI redesign — perf notes

## Baseline (code audit, pre-fix)

| Hotspot | Behavior |
|---|---|
| Chat stream | New messages array + BroadcastChannel on every SSE chunk |
| Chat markdown | ReactMarkdown + rehype-highlight on every streaming frame |
| Auto-scroll | `scrollIntoView({ behavior: "smooth" })` on every messages change |
| Project layout | `setInterval(800ms)` polling chat stream banner |
| Logs | `setInterval(2500ms)` always while mounted |
| Deployments | Poll 2s/5s even when tab hidden |
| App shell | Animated/blurred sky + heavy ink panel shadows on every page |
| Chat page | ~1k-line monolith; full DOM for all messages |
| Settings | Flat 2-col mix without section anchors |

## After

| Change | Effect |
|---|---|
| Stream chunk batching (rAF) | UI notifications ~1/frame instead of per token |
| Broadcast throttle 120ms | Cross-tab sync cheaper during stream |
| Plain text while streaming | No markdown/highlight until turn completes |
| Stick-to-bottom scroll | No forced scroll when reading history; `auto` only |
| `subscribeProjectStreams` | Replaces 800ms banner poll |
| Logs pause + visibility | No poll when tab hidden or paused; 4s interval |
| Log preview cap | Max 800 lines / 200k chars in DOM preview |
| Deployments visibility gate | Skip poll callbacks when document hidden |
| Flatter shell | No glass/blur/orbs in app chrome |
| Chat components split | `message-list`, `message-item`, `tool-activity-feed`, `execution-report` |
| Virtualized message list | `@tanstack/react-virtual` — only visible rows in DOM |
| Settings sections | Основное / Секреты / Сервисы / Публикация / Опасная зона + hash nav |
| Files viewer | Lazy on click; clear on tree nav; race-safe load; 200k char preview cap |

## Remaining / not measured in CI

- Chrome Memory/Performance heap snapshots were not run in this session — re-measure locally (steps below).
- No frontend test runner in `package.json`; `splitReport` is a pure helper in `message-item.tsx` if you add Vitest later.
- Services section is informational only (no list API on the frontend).

## How to re-measure locally

1. Chrome DevTools → Performance: record a chat turn with streaming.
2. Memory → heap snapshot before/after 3 project tab switches.
3. Network: confirm logs/deploy polls stop when tab is backgrounded.
4. `npm run build` and open `/app` in production mode for realistic paint cost.
5. Long chat (100+ messages): confirm message list keeps DOM node count roughly constant while scrolling.

Frontend automated tests are not configured in this package (`package.json` has no `test` script).

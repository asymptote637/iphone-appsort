---
name: iphone-appsort
description: "使用 AppSort 本地 Mac 工具读取 iPhone 的使用次数、预览主屏幕排序并验证应用结果。适用于 USB 连接的 iPhone 主屏幕整理；不是在 iPhone 后台运行的第三方启动器。"
---

# iPhone AppSort

Locate the AppSort project next to this packaged skill: its root is two levels above this SKILL folder, containing `appsort/`, `Start AppSort.command`, and `README.md`. If installed elsewhere, resolve the user's AppSort checkout before executing commands. Read README for installation and OS limits.

Use `<root>/bin/appsort` (or `<root>/.venv/bin/python -m appsort`) from the project root. Commands share the GUI's validation and persistence. Prefer `devices`, `read --udid <chosen>`, `copy-usage`, `usage --stream <confirmed-stream> --days 7`, and `propose --metric opens --days 7 --capacity 8 --widgets separate` when the user wants the two-row preset. Match the user's rules instead of assuming every layout needs two rows: `--metric opens|seconds|recent`, `--capacity 1..24`, `--page-limit 1..15`, `--folders flatten|preserve`, `--widgets keep|separate`, and repeated `--pin <bundle-id>` are supported. Recency requires timezone-aware last-open records. Named profiles, search, CSV import/export and JSON export are available in the GUI. The GUI is `serve` and listens only on 127.0.0.1.

Essential invariants:
- Confirm which USB UDID and synced stream belong to the user's phone. A metadata build number matching the connected phone and a recent sync is supporting evidence, not a substitute for an explicit device choice when ambiguous.
- Counts come from observed foreground entries, including returns, not process cold starts. Display the actual newest record time. Do not fill missing usage with examples or rank pickups as all launches.
- Raw plist files preserve dates and widget records. Never convert a widget layout through cfgutil. Sort keeps Dock fixed; the two-row preset puts intact widget records on a separate first page and at most 8 app icons on the top two rows of each remaining page. Widget moves must match the selected policy; avoid direct edits bypassing inventory/duplicate checks.
- A successful command exit is not proof of an applied phone layout. Batch application is gated by a live swap and restore for the exact UDID, iOS version and backend. Use the recorded `verified` readback status and retain failed/partial evidence.
- iOS may move App Library Only icons back onto the Home Screen during the first write. If that happens, disclose the names and changed page count, stop the old batch proposal, and prepare a revised reviewable result. Raw APIs cannot guarantee restoring the library-only state or hidden-page settings.
- `--yes` suppresses the CLI prompt; use it only when the user has authorized that concrete phone write. An earlier request just to inspect or build the tool does not authorize bulk rearrangement.

Private state lives under `state/`: originals, backups, usage, icons and transactions. Preserve it locally. Profiles in `state/profiles.json` include local settings and pins. Source ZIPs must exclude state and screenshots with real user app data. A demo server uses separate `demo-state/` and cannot write to phones.

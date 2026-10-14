# Changelog

## 0.1.0 — 2026-10-14

First public release of AppSort for iPhone Home Screen organization from a Mac.

- Rank by observed opens, accumulated foreground time or most recent foreground record over 7 or 30 days.
- Offer four editable layout presets: two rows, full pages, preserved folders and recent apps.
- Set any 1–24 icon capacity and 1–15 page budget; group only the necessary lowest-ranked tail when safe.
- Keep Dock fixed, preserve or flatten folders, and preserve widget positions or use a dedicated first page.
- Pin and search apps, save and load named local profiles, import timestamped usage CSV, and export CSV/JSON.
- Save raw plist backups, verify writes by reading back, and gate batch application on a successful live swap and restore.
- Offer an independent, narrowly scoped Screen Time copy helper for macOS permission attribution.
- Include a synthetic online/local demo, bilingual documentation, a Codex skill, contribution guides, launch drafts and CI.
- Check 62 tests and 288 hosted/desktop policy comparisons with simulated data.

### Known limitations

App Library Only icons may return to the Home Screen after the first write. Their library-only state and hidden-page settings cannot be guaranteed by a layout backup. Live write validation covers one iPhone 17 / iOS 27.0 (24A437); other versions need their own capability test. The cfgutil route has not been live-tested in this release.

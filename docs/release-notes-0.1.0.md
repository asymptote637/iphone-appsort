AppSort helps Mac users arrange an iPhone Home Screen from usage records, with a reviewable preview and a verified write workflow.

**[Try the synthetic online demo](https://asymptote637.github.io/iphone-appsort/demo/)** · **[中文说明](https://github.com/asymptote637/iphone-appsort/blob/main/README.zh-CN.md)**

- Choose opens, time or recency; four editable presets; 1–24 icons per page and a 1–15 page budget.
- Keep or flatten folders, keep widget positions or use a dedicated first page, and keep Dock fixed.
- Pin and search apps, save local profiles, import usage CSV, and export CSV/JSON.
- Back up before writing; require a live swap and restore before batch application; read back the result.
- Use the Mac browser UI, CLI or bundled Codex skill. The local demo needs only Python 3.11+.

Download **iphone-appsort-0.1.0-source.zip**, extract it, and follow the README. macOS phone integration also requires the dependency setup, an unlocked trusted USB phone, and synced usage records or an explicit CSV import. The compiled usage helper needs Full Disk Access. The ZIP contains source and synthetic demo media; it is not a notarized Mac app or an iPhone app.

Validation: 62 automated tests and 288 hosted/desktop policy comparisons; browser interaction checks; Swift helper compilation. Native swap, restore and the two-row configuration were verified on one iPhone 17 / iOS 27.0 (24A437). Other configurations and devices need their own live capability checks.

Known limitation: the first layout write can bring App Library Only apps back to the Home Screen. Layout backups cannot guarantee restoring library-only state or hidden-page settings. cfgutil is implemented but has not been live-tested for this release; it is blocked for widget layouts.

The checksums in **SHA256SUMS.txt** cover the source ZIP. License: GPL-3.0-or-later, with retained upstream notices.

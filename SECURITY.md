# Security and privacy

AppSort processes layouts and usage locally. The desktop UI listens only on 127.0.0.1 and protects APIs with a session token, Host validation and origin checks. Its usage helper reads only synced App.InFocus streams and device metadata; Full Disk Access is still a broad macOS permission and should be granted only after reviewing the helper source.

`state/` contains private phone identifiers, layouts, app artwork, usage and backups. It is excluded from Git and release bundles. The online demo contains only hardcoded synthetic records and has no connection to the desktop app or a phone.

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/asymptote637/iphone-appsort/security/advisories/new). If that feature is unavailable, open an issue with a high-level description and request a private channel before sharing exploit details or private data. Do not attach real pairing records, usage databases or credentials.

Device writes are consequential: raw layout backups do not restore all SpringBoard settings, and App Library Only icons can reappear on the Home Screen. A successful process exit is insufficient; the tool uses device read-back to decide whether a write actually matched the preview.

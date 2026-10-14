# Contributing

AppSort combines configurable policies with a careful device workflow: reliable local evidence, clear previews and honest device compatibility matter more than broad compatibility claims.

Start with the [demo](https://asymptote637.github.io/iphone-appsort/demo/), [issues](https://github.com/asymptote637/iphone-appsort/issues) or [Discussions](https://github.com/asymptote637/iphone-appsort/discussions). Small fixes and documentation improvements are welcome.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_demo.py
python3 scripts/build_release.py --check-only
```

Python 3.11+ runs the core tests. Node 22+ enables the hosted-demo syntax and 288-policy parity checks; CI runs both. The tests use simulated phones; they do not need device dependencies or write a real phone. To test USB integration, install dependencies on a Mac and use your own authorized phone, with a backup and a clearly reviewed test.

Useful first contributions:
- Translate interface strings without changing ranking or write behavior.
- Improve the first-run explanation for stale or ambiguous synced devices.
- Add fixtures for documented SEGB format differences, stripped of personal data.
- Improve keyboard navigation or narrow-screen layout in the preview UI.

For a pull request, describe the problem, the observable behavior change, and what you tested. Keep unrelated changes separate. Changes to device writes need meaningful tests for failure, partial application and read-back verification.

Do not submit phone identifiers, pairing records, raw usage streams, real screenshots, app inventories, tokens or `state/`. Use synthetic data or a minimal anonymized fixture. Preserve upstream attribution and GPL-3.0-or-later licensing.

# Validation and compatibility

The first public release was exercised on one iPhone 17 running iOS 27.0 (build 24A437), on 2026-10-14. Its USB read, native layout swap, restore and final sorting operation were checked against independent phone read-back.

The final verified layout had a dedicated page of two intact widget stacks and fourteen app pages with eight icons across the top two rows per page. Dock order and the complete represented app inventory were preserved; the two tail entries shared a final folder to stay within the tested page budget.

## What the live test revealed

- The first native write caused nine App Library Only icons to return to the Home Screen. The program classified the resulting inventory mismatch as partial, stopped batch application and restored the represented original order. The API did not restore library-only state.
- With the complete resulting inventory, a fresh swap and restore matched read-back.
- A sixteen-page proposal was normalized to fifteen pages by that device, with the overflowing entry placed on the widget page. The program again reported partial application. The final tail grouping avoided this observed normalization and preserved the two-row rule.
- Actual synced Biome foreground records decoded successfully. They lagged current phone activity; the newest-record timestamp was shown rather than assuming a complete real-time window.
- A Full-Disk-Access-authorized helper run independently copied records successfully. Its startup logs must be placed in temporary storage because xpcproxy opens them before the helper's permission identity applies.

## What automated tests establish

The 62 tests and 288 hosted/desktop policy comparisons check opens/time/recency, custom density and page budgets, profile persistence, CSV timestamps, ranking, bounded event aggregation, corrupt records, stable layout fingerprints, inventory preservation, widget policy, page budgeting, stale proposals, ignored/partial/unconfirmed writes, version changes, recovery boundaries, loopback API authorization and demo isolation. Simulated test success is software evidence, not a live compatibility result for another phone.

The additional customizable policies use simulated layouts and browser checks. The live device result above applies to the tested two-row configuration; it does not establish that every new configuration is accepted by iOS.

## Not verified

- Other iPhone models, iPad layouts or iOS versions.
- The optional cfgutil writer on a live device.
- Restoration of hidden Home Screen pages or App Library Only state.
- Long-term background operation; AppSort performs a deliberately initiated organization.

No personal device IDs, pairing material, real usage streams, private screenshots or backups accompany this public record. Demo images use entirely synthetic data.

# Contributing

Keep the project small and focused on local transcription of the Android My BMW journey list.

- Never commit credentials, VINs, addresses, account data, or real journey records. Fixtures must be fictional and sanitized. The repository ignore rules exclude captures, raw XML, generated reports, and review archives; keep sanitized fixtures explicitly tracked.
- Preserve source text and raw XML. Mark derived values with provenance; do not invent missing locations, times, or grouped trip legs.
- Do not add BMW CarData authentication or private API calls.
- Add focused `unittest` coverage for parser, merge, date, report, and launcher behavior when changing those areas. Install dependencies from `requirements.txt` first.
- Run `make test` and `python bmw_export_journeys.py --help` before proposing a change. Make tests are offline and must not depend on ADB or a phone.
- Explain any real-device validation separately from offline fixture tests.

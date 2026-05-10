# Design Notes

- This is a Trellis `deep` task because it spans backend tasks, AI runtime, frontend monitoring, Docker/ops, migrations, and release evidence.
- Parallel agents are split by disjoint ownership slices. The parent agent owns final integration, verification, and release-readiness judgement.
- Compatibility cleanup means removing old live contracts such as alternate response shapes, snapshot-field fallbacks, or retired aliases. It does not mean removing normal failover, i18n fallback, typed error display, or safe operational fallback.
- AI dialogue changes remain bounded by `.trellis/spec/ai-runtime/testing-discipline.md`: structural and behavioral checks can produce a verified candidate, but full AI dialogue production acceptance still needs archived real-dialogue smoke with real provider credentials or an approved replay.

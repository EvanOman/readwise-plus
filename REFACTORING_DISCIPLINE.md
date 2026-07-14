# Refactoring Discipline — Michael Feathers, *Working Effectively with Legacy Code*

This restructure is a legacy-code exercise. Every stage MUST honor these rules. They override speed, cleverness, and convenience. A stage that cannot follow them is too big — split it.

1. **Legacy code is code without tests.** No structural change ships without a test that would fail if behavior regressed. If code isn't covered, cover it *before* moving it.

2. **Characterization tests pin ACTUAL behavior, not intended behavior.** They record what the code does *today* — quirks and bugs included. When a test captures surprising or wrong behavior, keep it and annotate `# characterizes current (buggy) behavior`. Do not "correct" it in the same breath.

3. **Cover and Modify — never Edit and Pray.** Get code under test first, then change it. If it's untestable as written, introduce a *seam* (a place to substitute behavior without editing in place) and break the dependency minimally, rather than rewriting blind.

4. **Refactoring preserves behavior — full stop.** Never change structure and behavior in the same commit. Move / rename / extract / re-layer are behavior-neutral. Bug fixes and feature changes are SEPARATE, clearly-labeled commits, each with a test that *demonstrates* the change. (Example: the `save_to_reader(category=…)` bug is fixed in its own commit, only after a characterization test locks the current — broken — payload.)

5. **Small steps, always green.** Every step ends with `just fc` passing (format, lint, type, test). Prefer many tiny verifiable moves to one big leap. Never weaken the Justfile, delete/skip a test, or widen a `ty` exclusion to make a step "pass."

6. **Preserve the public contract with shims, not by freezing internals.** Old imports and return values survive through re-exports and compatibility wrappers whose behavior is pinned by characterization tests. Internals may change freely; the observable surface may not — until 1.0.

7. **The Legacy Change Algorithm**, applied to each move: identify change points → find test points → break dependencies (seams) → write tests → make the change → refactor.

8. **When in doubt, add a test.** A refactor you can't cover is a refactor you shouldn't make yet.

> Resource clients know endpoints. Operations know intent. Adapters know protocol. Tests know what must not change.

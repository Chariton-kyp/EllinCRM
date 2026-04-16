<!--
Thanks for contributing! Please give reviewers enough context to
evaluate the change without having to dig.
-->

## Summary

<!-- 1–3 sentences. What does this PR do and why? -->

## Type of change

<!-- Keep the ones that apply; delete the rest. -->

- [ ] Bug fix (non-breaking change that resolves an issue)
- [ ] New feature (non-breaking change that adds capability)
- [ ] Breaking change (existing behaviour changes in a user-visible way)
- [ ] Refactor / internal cleanup (no behaviour change)
- [ ] Docs / tooling / CI only

## Linked issues

<!-- "Closes #123" or "Refs #456". Leave blank if none. -->

## How I tested this

<!--
Concrete commands the reviewer can re-run, and any tricky edge cases
you exercised manually. "Ran CI" is not enough on its own.
-->

- [ ] `ruff check app/` and `ruff format --check app/ tests/` pass
- [ ] `pytest tests/ -m "not integration"` passes locally
- [ ] Frontend: `npm run type-check && npm run test:run && npm run build`
- [ ] Verified the change in the UI (describe: _________)

## Screenshots / recordings

<!-- For UI changes, paste a before/after screenshot or a short GIF. -->

## Checklist

- [ ] I followed the style enforced by `ruff` (backend) / `eslint`, `tsc` (frontend).
- [ ] I added or updated tests where meaningful.
- [ ] I updated docs / README / migration notes if user-visible behaviour changed.
- [ ] No real secrets, personal data, or proprietary fixtures are added to the tree.

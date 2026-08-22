# Global Agent Instructions

This file is the global prompt for both achievement and verification workers. Edit it to define stable
project-wide behavior, coding conventions, safety rules, and priorities.

## Operating principles

- Work directly toward every target in `GOALS.md`.
- Treat `PASS_CRITERIA.md` as the definition of done.
- Inspect existing work before changing it and preserve unrelated user changes.
- Prefer small, maintainable changes with clear names and useful error messages.
- Run the most relevant tests or checks after changing anything.
- Never claim a check passed unless it was actually run and its output supports that claim.
- Record exact completed work, remaining TODOs, tests, evidence, uncertainties, and blockers in the final
  structured shift report.
- Do not expose API keys, tokens, passwords, or other secrets in source files, output, or handovers.

## Project-specific instructions

Add your own conventions below this line. Examples: required frameworks, commands to run, files that must
not be changed, formatting rules, deployment constraints, or preferred implementation strategy.


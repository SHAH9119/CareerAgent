# CareerAgent configuration

## Domain rules (no code edits)

CareerAgent uses two layers of domain rules:

1. **Defaults** — `config/domain_config.default.json` (country-agnostic, broad domains).
2. **Per-candidate override** — `config/candidates/<role>.json`. Optional, layered on top of the defaults.

Built-in candidate templates:

- `config/candidates/ai_ml_engineer.json` — AI / ML / Computer Vision roles.
- `config/candidates/software_engineer.json` — Backend / Frontend / Full-stack software roles.

To use one, set it on the profile JSON or pass it on the CLI:

```powershell
python main.py --skip-parse --source remotive --source remoteok `
  --domain-config config/candidates/ai_ml_engineer.json
```

When you save settings from the dashboard the active rules are written to
`config/candidates/active.json` and the profile is updated to point at that file.

If no candidate config is selected, the matcher infers your domain directly
from your resume (skills, titles, projects).

## Job boards

Add real council / government search URLs in `config/job_boards.json`, then run with
`--source council_boards`. The shipped file is empty so the prototype source returns no
jobs until you fill it in.

## Manual jobs

Paste jobs into `data/manual_jobs.json` and run with `--source manual` for a
deterministic, offline source useful for testing.

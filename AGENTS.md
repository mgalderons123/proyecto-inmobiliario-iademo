# Incremental Project Workflow

Use the codebase knowledge graph before broad file searches. Read only the
symbols and neighboring code needed for the current change.

Before verification, inspect changed files and their callers/tests. Run the
smallest relevant test set first. Run the full suite when settings,
dependencies, middleware, authentication, permissions, models, migrations, or
shared infrastructure change, and before integration or deployment.

Use `./scripts/verify-changed.py -- <pytest args>` for repeatable local test
runs. A previous success may be reused only when its complete source,
dependency, command, Python, and settings fingerprint is unchanged. Never cache
failed results.

Use `./scripts/compare-envs.py` to compare the public landing in development
and QA. The script normalizes static asset fingerprints and reuses only a
successful comparison whose local source fingerprint and QA image ID are
unchanged.

Do not store credentials, environment file contents, private media, database
data, or authenticated responses in local verification caches.

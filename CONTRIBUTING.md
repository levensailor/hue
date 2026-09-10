# Contributing

## Branch and pull request

1. Create a feature branch from `main`. Do not commit directly to `main` for new work.

```bash
git checkout main
git pull
git checkout -b feature/short-description
```

2. Make the change. Keep names, hosts, ports, and paths in environment variables.
3. Update `CHANGELOG.md` when the change is a feature, not a bug fix. Use the same description as the commit message and include a date.
4. Commit on the feature branch.

```bash
git add -A
git commit -m "Explain why this change exists."
```

5. Push the branch and open a pull request that explains why the change should land.

```bash
git push -u origin HEAD
```

In the pull request, describe:

- Why the change should be added
- How you verified it (Hue pairing, SSL device selection, Logic Pro input, lightshow mode)
- Any Entertainment area or audio-device assumptions

6. Wait for review. Merge only after the pull request is approved.

## Local notes

- Do not commit `.env`, `data/credentials.json`, virtualenvs, or log files.
- Hue pairing requires a physical press of the bridge link button.
- Audio capture needs macOS Microphone permission.

# COMP3500 VoteLab / 投票系统基础原型

Increment 1: single choice and 0–5 scoring. **Local classroom prototype, not a deployed service or a finished project.** AI-assisted starter implementation for the team to review, understand and extend. Do not claim this code was independently written by team members.

## Run / 启动

Install Python 3.11 or newer, then open a terminal in this folder:

```text
python app.py
```

Open http://127.0.0.1:8000 in a browser. No third-party packages are needed. The SQLite database is created in `data/`, excluded from Git. Stop with Ctrl+C. Windows may use `py app.py` instead.

```text
python -m unittest -v
```

Run tests from this folder. Tests use temporary databases and do not modify the demo database.

## Demonstrate / 演示步骤

1. Register a fictional phone account (8–15 digits) and a password of at least 8 characters. Phone ownership is **not verified**; do not use real personal details.
2. Create an event with at least two distinct candidates; select SINGLE or SCORE, results visibility, and duration in minutes.
3. Review the draft preview. Confirm publication to start voting immediately. Preview itself cannot save ballots. Draft editing is pending; create another draft to correct a mistake.
4. Vote using another demo account, e.g. a separate browser or private window. SINGLE requires one candidate; SCORE requires an explicit integer 0–5 for every candidate. Zero is valid, unanswered is not.
5. A successful ballot is shown on the event page. A second submission in the same round is rejected.
6. Close as the creator, or wait for the deadline. Deadline checks happen on every request and again inside the ballot transaction; there is **no background scheduler** yet.
7. The creator can review closed totals and publish them. Public published results are accessible to everyone; private results remain creator-only in this increment. No UI displays who voted for whom.

The end time is displayed in UTC. Duration starts when publication is confirmed, not when the draft is saved. The built-in server binds to localhost only. Do not expose it publicly.

## Files / 文件

- `app.py`: WSGI pages, account sessions, lifecycle, vote validation and counting.
- `schema.sql`: users, sessions, elections, candidates, rounds, ballots, choices and lifecycle audit.
- `test_app.py`: automated acceptance and failure-path checks.
- `docs/`: requirements, test mapping, current progress, meeting agenda and team workflow.

## Known limits / 当前边界

Not yet implemented: multi-selection, majority runoff, RCV, award quotas / award allocation, tie runoff / joint approval, administrator role, candidate review, draft editing, separate vote-confirmation page, one-time end-time extension, SMS / school ID verification, PDF export, scheduled starts, background closure jobs and robust network-timeout recovery UI. They remain backlog items, **not completed requirements**.

Result-publication behavior is a provisional demo choice: creator publishes after closure. The team's exact publication permissions remain open. Private controls **result access**, not event participation; private invitations are not implemented. Ordinary database operators can correlate ballots and choices internally: separate tables do **not** guarantee anonymity. The result UI only shows aggregates.

The local server is single-process and not load tested. Password hashing, server-side sessions, CSRF checks, escaping, transactions and constraints provide basic protections but not a full security assessment. SMS verification, rate limiting, HTTPS, production secrets, backups and deployment require further work.

## Collaboration / 小组协作

See `docs/TEAM_WORKFLOW.md`. Preserve other coursework in the repository root; this project lives only in `voting-system/`.

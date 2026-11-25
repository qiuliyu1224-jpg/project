# VoteLab

Local Python + SQLite voting and entry-evaluation prototype.

Current version: **0.4.10**.

[Download Windows, Apple Silicon or Intel Mac](https://github.com/qiuliyu1224-jpg/project/releases/tag/votelab-v0.4.10-team-test).
The release is published only after all three native builds and checks succeed.
Safely quit the running older VoteLab before upgrading, and keep the data folder.

The home page has one complete interactive entry-evaluation demo and two display
examples. The demo includes local images, optional ratings, review, editing,
temporary submission/results and restart. The guide and empty list open the same
demo. Demo actions never enter real events or ballot records.

Login, language controls on auth and workspace pages, independent entry practice,
real voting/review, backups, exports and stable list filters remain.

For development, install voting-system/requirements.txt and run
`python voting-system/run_votelab.py`. Native ZIP packages include their runtime.

Checks: `npm ci`, `npm run browser:install`, `npm run tools:check`,
`npm run test:ui`, `npm run test:onboarding`, `npm run test:demo`,
`npm run test:filters`. These use disposable test data. Playwright/FFmpeg are
development tools, not user requirements for the packaged application.

See [0.4.10 changes and validation](voting-system/docs/VERSION_0410.md),
[source notes](voting-system/README.md). This classroom prototype does not provide
cloud sharing or real SMS identity verification.

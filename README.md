# VoteLab

This branch packages VoteLab for local team testing. Download the ZIP for Windows x64, macOS Apple Silicon or macOS Intel from the [0.4.7 team test release](https://github.com/qiuliyu1224-jpg/project/releases/tag/votelab-v0.4.7-team-test). Extract the ZIP and follow the included instructions.

Version 0.4.7 adds local backup/restore and safe quit, aggregate CSV and SVG/PNG chart downloads, and explicit tie/no-vote revotes that preserve round history. Desktop launches open English, with Chinese still available. Existing data stays in the same user data directory. Before the first upgrade from an older release, quit its VoteLab process. Afterward use **Local data & upgrades → Quit VoteLab safely** before upgrading. Closing a browser does not stop the server.

See [0.4.7 changes and boundaries](voting-system/docs/VERSION_047.md). This remains a local classroom prototype, without cloud sharing or real SMS verification.

If an earlier VoteLab is already running, open http://127.0.0.1:8765/ to use it. On Mac, quit the known VoteLab process in Activity Monitor before updating. Keep the existing database and backups.

See the [VoteLab source and project notes](voting-system/README.md) for features, development setup and tests.

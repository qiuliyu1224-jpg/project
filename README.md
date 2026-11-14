# VoteLab

This branch packages VoteLab for local team testing. Download the ZIP for Windows x64, macOS Apple Silicon or macOS Intel from the [0.4.5 team test release](https://github.com/qiuliyu1224-jpg/project/releases/tag/votelab-v0.4.5-team-test). Extract the ZIP and follow the included instructions.

Version 0.4.5 addresses repeated launches: opening an already running 0.4.5 app reopens its existing page, while an unknown program occupying the requested port produces a clear startup error. Existing data stays in the same user data directory. Before updating from an earlier release, quit its VoteLab process first. Closing the browser does not stop the local server.

If an earlier VoteLab is already running, open http://127.0.0.1:8765/ to use it. On Mac, quit the known VoteLab process in Activity Monitor before updating. Keep the existing database and backups.

See the [VoteLab source and project notes](voting-system/README.md) for features, development setup and tests.

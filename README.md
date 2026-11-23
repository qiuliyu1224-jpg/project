# VoteLab

This branch packages VoteLab for local team testing. Download the ZIP for Windows x64, macOS Apple Silicon or macOS Intel from the [0.4.6 team test release](https://github.com/qiuliyu1224-jpg/project/releases/tag/votelab-v0.4.6-team-test). Extract the ZIP and follow the included instructions.

Version 0.4.6 explicitly opens the English homepage on each desktop launch, including browsers with an old Chinese preference. You can still switch to Chinese afterward. The sidebar shows the exact version. Repeated launches reuse only the same app version and data directory. Existing data stays in the same user data directory. Before updating from an earlier release, quit its VoteLab process first. Closing the browser does not stop the local server.

If an earlier VoteLab is already running, open http://127.0.0.1:8765/ to use it. On Mac, quit the known VoteLab process in Activity Monitor before updating. Keep the existing database and backups.

See the [VoteLab source and project notes](voting-system/README.md) for features, development setup and tests.

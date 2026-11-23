# VoteLab 0.4.7 — Local workflow update

- English desktop startup and full version display from 0.4.6 are retained.
- Double-click the app, then use **Local data & upgrades** in the sidebar.
  **Quit VoteLab safely** stops this instance so the next version can start.
  Closing a browser alone does not stop the server. An older running version
  must still be quit before the first upgrade to this release.
- **Back up now** saves a consistent SQLite snapshot in the local data folder's
  `backups` directory. Startup backups remain enabled. Backups contain private
  account and ballot records; do not publish them or add them to GitHub.
- **Restore all data** requires typing RESTORE. It validates the selected backup,
  migrates an independent copy, saves a before-restore backup, then replaces the
  database. Corrupt, incompatible or newer-schema backups are refused. All
  sessions are cleared. This replaces the whole local database, not one event.
  Only files in the local backups folder are listed; to restore a copied backup,
  place it there with its original `voting-TIMESTAMP.sqlite3` name.
- Result pages export aggregate CSV (all RCV count steps included), SVG with
  original labels, and 2x PNG of the displayed chart. No voter identity or
  individual ballot link is exported. Private, unpublished and invited results
  keep the same access checks. CSV preserves zero vs skipped ratings and
  neutralises formula-like text for spreadsheets.
- Creators can start an explicit fresh ballot for ties or no-vote rounds.
  A reason, deadline and confirmation are required. Choice/rating joint leaders
  enter; majority cutoff ties include everyone at or above the cutoff; RCV
  restarts its whole eligible roster. The method is unchanged, old ballots stay
  in history, and stale round forms are rejected. No random elimination, manual
  winner assignment, award allocation or joint approval is introduced.
- Local tools require the launcher's per-process capability, not just a website
  account. Restore, application requests and deadline maintenance are serialised
  so database replacement cannot overlap a request or background DB connection.
- Still a local classroom prototype: no cloud sharing or real SMS verification.
  Native packages are Windows x64, macOS Apple Silicon and macOS Intel.

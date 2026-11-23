# VoteLab 0.4.6 - English desktop entry and eight-item recheck

## Why 0.4.5 could still open in Chinese

The 0.4.5 routes defaulted to English only when a valid language preference was absent. A browser with `lang=zh` retained Chinese indefinitely. This meant changing the default alone did not satisfy the desktop expectation that double-clicking VoteLab opens English.

Version 0.4.6 opens `/?lang=en` on both first and repeated desktop launches. The home route applies that explicit language and saves the preference, without clearing the login session, activities or ballots. Manual Chinese switching still works during navigation. Plain browser navigation without the launch parameter continues to respect the selected preference.

The sidebar displays the exact app version. The launcher identity endpoint also reports a version: a running older app is no longer silently reused by a newer launcher. Close the known old VoteLab before upgrading; never delete the data folder to change language or solve port conflicts.

## Acceptance checklist

| Requirement | Rechecked behaviour |
|---|---|
| Automatic results and charts | New public events publish when the final round ends. Creator-only results stay private. Bar, horizontal bar and line charts use the same count results and permissions. Legacy publication choices remain unchanged until explicitly edited. |
| English default | Fresh browser is English; desktop launch explicitly overrides an old Chinese cookie. Chinese remains selectable. |
| Invitation-page back link | A deterministic link returns to Explore without depending on browser history. |
| Switch account | CSRF-protected POST ends only the current session and preserves records. |
| English interface and activity display | Static labels are English. Chinese display content is sent to the existing online translator; stored originals and form values remain unchanged. Network/provider failures show an English failure state with View original and Retry translation. |
| Create-page back link | Creation returns to My events; editing returns to the relevant event. |
| Majority-runoff limit | The maximum-selection field is hidden and disabled outside single/multiple choice. Majority runoff enforces one choice per voter per round on the server. |
| Formal templates | Activity templates, Custom activity, Entry evaluation and Single-choice voting. |

## Data and verification boundaries

- Reuses the existing per-user data directory and startup backup mechanism. No destructive data migration is introduced.
- Automated tests use isolated temporary databases. Browser fixtures contain fictional accounts and activities only.
- Provider success and failure are both tested with controlled responses. A mocked translation result is not evidence of a real online service's availability or translation quality.
- Native Mac packages must pass macOS runner tests and package restart/persistence checks before being published. A local Windows check alone is not a Mac check.

This release does not add chart downloads, author-corrected translations, cloud hosting or real SMS.

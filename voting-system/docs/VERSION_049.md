# VoteLab 0.4.9 — Requirements, changes and validation

## Feedback and acceptance criteria

| ID | Feedback / requirement | Implementation | Evidence |
| --- | --- | --- | --- |
| R01 | Start with login; retain valid sessions and both language controls | web4.py, ui4.py, local_tools.py, launcher | test_onboarding.py; browser registration, login and reopening |
| R02 | Explain where Quick guide is after successful login/registration | short-lived server marker; per-account browser dismissal | browser hint visible, dismissible, not repeated on subsequent login |
| R03 | Include entrant as well as voter and creator | guide.js three goals, five explanations each | each guide read to completion; actual entrant review/resubmission flow |
| R04 | Finish the guide without saving, submitting or opening voting | independent explanation navigation and finish at every step | no business POST; unchanged DB; unsaved form retained |
| R05 | Explain unavailable activities and provide safe practice | availability counts and in-memory modal practices | zero/skip distinction, local image preview, no POST or DB writes, mobile fit |
| R06 | Explain known older-version startup conflicts | token-authenticated identity diagnostics and Windows message dialog | exact-version reuse and rejection of foreign/older identity; native process tests |

## Validation

- Follow-up list fix: status tabs filter in place and retain the search term.
  A reserved list area prevents short/empty results from clamping page scroll.
  Direct URLs and ordinary non-JavaScript links retain server-side visibility.
  Desktop/mobile browser checks: 24 passed, including Back, search, empty results
  and no document reload; 27 affected Python checks passed.
- Local Windows verification: 142 Python checks, 37 existing browser checks and
  51 new-user browser checks passed. The extracted Windows package also passed
  launch, exact-instance reuse and persistence checks before and after restart.
- This local ZIP reuses the hash-verified 0.4.8 CPython/Pillow runtime with updated
  0.4.9 application sources. No 0.4.9 native macOS package has been built yet.
- Python: `cd voting-system && python -m unittest discover -v`.
- Existing workflow/motion: `npm run test:ui`.
- New-user paths: `npm run test:onboarding`.
- All browser fixtures use synthetic accounts and independent temporary SQLite files.
- Tests cover normal and unavailable states, form preservation, English/Chinese,
  390px mobile layout, reduced motion, actual review, rejection and resubmission.
- Practice sends no business POST. It does not rely on a hidden demo flag in real
  vote endpoints. No data migration or schema change is required (schema stays 47).

## Scope and limits

These are developer-run automated checks, not evidence of a formal user acceptance
study or production audit. Organise a separate teammate trial and record actual
observations before claiming improved task completion time. Native CI checks cannot
claim a Finder GUI run, macOS 14.5 validation, notarisation or cross-device sharing.
Guide and demo progress can be lost on closing/reloading the browser. No browser
storage is needed to finish explanations, but dismissal memory needs localStorage.
Language preferences persist in the existing cookie; explicit `/?lang=en` links
still override the current page language deliberately.

## Upgrade

Quit the running old instance through Local data & upgrades > Quit VoteLab safely.
Then extract and start 0.4.9. Keep AppData/Local/VoteLab (Windows) or the existing Mac
Application Support folder. No automatic process termination or user data deletion.

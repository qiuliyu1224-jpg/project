# VoteLab

Local Python + SQLite voting and entry-evaluation prototype.

[Download VoteLab 0.4.8 for Windows or macOS](https://github.com/qiuliyu1224-jpg/project/releases/tag/votelab-v0.4.8-team-test).
Quit the previous VoteLab process before upgrading; keep the existing data folder.

0.4.8 adds a warm ivory/walnut interface, large local artwork, two five-step guides,
star/submit feedback and a small ended-event dialog. It retains the original
general-purpose voting rules, local data, backups, restore, exports and revotes.

Project development tools: `npm ci`, `npm run browser:install`,
`npm run tools:check`, `npm run test:ui`. Playwright/FFmpeg are pinned in the root
package files; they are not required by users of the native ZIP packages.

See [0.4.8 details](voting-system/docs/VERSION_048.md) and
[source/project notes](voting-system/README.md). This is a local classroom
prototype, without cloud sharing or real SMS verification.

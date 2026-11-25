# VoteLab

## Download and Run

**Current release: 0.4.10.** Download the ZIP for your computer from the
[release page](https://github.com/qiuliyu1224-jpg/project/releases/tag/votelab-v0.4.10-team-test).

| Your computer | Download |
| --- | --- |
| Windows, 64-bit | [VoteLab-0.4.10-Windows-x64.zip](https://github.com/qiuliyu1224-jpg/project/releases/download/votelab-v0.4.10-team-test/VoteLab-0.4.10-Windows-x64.zip) |
| Mac with an Apple M-series chip | [VoteLab-0.4.10-macOS-Apple-Silicon.zip](https://github.com/qiuliyu1224-jpg/project/releases/download/votelab-v0.4.10-team-test/VoteLab-0.4.10-macOS-Apple-Silicon.zip) |
| Mac with an Intel processor | [VoteLab-0.4.10-macOS-Intel.zip](https://github.com/qiuliyu1224-jpg/project/releases/download/votelab-v0.4.10-team-test/VoteLab-0.4.10-macOS-Intel.zip) |

The ZIP packages include their runtime. You do not need to install Python, Node.js,
Playwright or FFmpeg to use them.

### Windows

1. Download the Windows ZIP and extract **all files** to a new folder.
2. Open the extracted folder and double-click **Start VoteLab.bat**. Windows may
   display the name as **Start VoteLab** when file extensions are hidden.
3. Wait for the browser to open. Keep the launcher running while using VoteLab.

Do not launch the application from inside the ZIP or move the startup file away
from its `app` and `runtime` folders.

### Mac

1. In **Apple menu > About This Mac**, check whether the computer has an Apple
   M-series chip or an Intel processor. Download the matching ZIP.
2. Extract the ZIP and open the extracted folder.
3. Double-click **VoteLab.app** and wait for the browser to open.

This classroom build is not notarised by Apple. If macOS blocks it, consult the
included Mac first-run instructions and your device administrator where relevant.

### If the browser does not open

Use the local address shown by the launcher, normally
`http://127.0.0.1:8765/`. VoteLab must be running for that address to work.
The address refers to the application on your own computer, not a shared website.

## First Use

1. Select English or Chinese on the login or registration page.
2. Create an account using a fictional phone number that matches the selected
   country format and a password used only for this demonstration.
3. Request the demonstration verification code. The code appears on the page;
   no SMS is sent and phone ownership is not verified.
4. Sign in. The application opens Explore. Language switching remains available
   in the workspace, and your selected language is retained.
5. Open **Quick guide** in the upper-right corner whenever you need help.

The same account can create events, submit entries and vote. Separate accounts
for these activities are not required.

## Try the Example Before Creating an Event

- **Entry evaluation** is an interactive demo. Open **Try the interactive demo**,
  browse three illustrated entries, rate at least one, review your choices and
  submit a demo ballot. You can return to edit, view demo results and try again.
- **Proposal voting** and **Project showcase** are display examples. Their
  buttons open explanations and optional creation guidance, not a live ballot.

In the rating demo, zero is a valid score. Skipped entries are not counted as
zero. Images can be enlarged. Demo results contain only your current demo ballot,
with no preset votes. Demo activity never enters real events, ballot history,
totals or exports. Refreshing, closing or restarting the demo clears its progress.

The voter guide and the empty-event practice button open the same interactive
demo. Entry-submission practice is a separate form exercise; it sends no real
application for review. Guides can be read or finished without saving or submitting.

## Use a Real Local Event

| Goal | Basic steps |
| --- | --- |
| Create an event | Choose **Create event**, set the rules, add options or allow entry applications, then save and preview. Explicitly open applications or voting when ready. |
| Submit an entry | Find an event accepting applications, check its deadline and access requirements, then submit an entry for review. Check **My entries** for the actual review status. |
| Vote | Open an event with voting available, follow its selection, rating or ranking rules, review the ballot, then confirm submission. |
| View results | Results depend on the event status, publication settings and access permissions. Available exports appear with the permitted results. |

Events, accounts and ballots are stored locally. Each computer has its own data.
An invitation code controls access to an event on that installation; it does not
transfer or synchronise events between computers. There is no cloud sharing.

## Update, Backup and Quit

1. In the running older version, choose **Local data & upgrades > Quit VoteLab
   safely** before starting a new version. Local management tools are available
   to the browser opened by the launcher.
2. Extract the new ZIP into a new folder. Keep the existing user data folder so
   that accounts, activities and ballots remain available.
3. Start the new version using its own startup file.

Closing the browser alone does not stop the background application. Use the local
management page for backup and upgrade tools. Do not delete the data folder or
stop an unrelated process to resolve a startup conflict.

## Source Code and Developer Setup

[Open the VoteLab 0.4.10 source branch](https://github.com/qiuliyu1224-jpg/project/tree/codex/votelab-0410).
The repository's default branch also contains earlier data-preprocessing coursework;
use the linked VoteLab branch for this software project.

The native packages are the simplest way to try the application. To run from source,
use Python 3.13 and Git, then run these commands from a terminal:

```text
git clone --branch codex/votelab-0410 --single-branch https://github.com/qiuliyu1224-jpg/project.git votelab
cd votelab
python -m pip install -r voting-system/requirements.txt
python voting-system/run_votelab.py
```

On a system where Python is named `python3`, use `python3` in place of `python`.
Pillow is the application dependency. The web application uses Python and SQLite.

## Checks and Validation

Run the Python checks from the source repository:

```text
cd voting-system
python -m unittest discover -v
```

For optional browser checks, return to the repository root, install Node.js with
npm, then run:

```text
npm ci
npm run browser:install
npm run test:ui
npm run test:onboarding
npm run test:demo
npm run test:filters
```

The local release checks passed 142 Python checks, 37 existing interface checks,
51 onboarding checks, 36 demo checks and 24 filter checks. Native Windows, Apple
Silicon Mac and Intel Mac builds passed their automated build and archive checks.
These are developer-run checks, not a formal user study or a production security
certification. Mac checks do not establish compatibility with every macOS version
or replace a first-run trial on a teammate's computer.

## Project Scope

VoteLab is a Software Engineering course prototype for entry evaluation, proposal
voting and project selection. It supports single/multiple choice, star ratings,
majority runoff and ranked-choice voting, together with entry review, rounds,
results and local data tools.

Use fictional demonstration details. This project does not provide real SMS
verification, verified school identity, cloud synchronisation or cryptographic
ballot anonymity.

## Team Contributions

All eight members discussed and agreed on the voting rules during group meetings. The team also jointly confirmed the need for language switching.

All members participated in user-oriented trials of versions 0.4.2-0.4.5. Members used the application, identified inconvenient steps and suggested improvements. Feedback included missing Back buttons, inconsistent English text, and a selection-limit field that did not match the majority-runoff rules. The team also discussed account switching and clearer result presentation. This feedback informed later revisions.

Each member prepared their own presentation section. The individual contributions below distinguish initial prototype work, presentation responsibilities and later implementation work.

| Member | Student ID | Contribution |
| --- | --- | --- |
| **Zhang Qiuyun** | 13796766 | Prepared the Implementation section and led later application development and integration. Guided, reviewed and followed up on the team's initial work. Independently proposed improvements to the interface, navigation, interaction feedback, user guides and demo flows, and implemented the team's language-switching requirement. Participated in early user trials and organised feedback into specific changes. Took sole responsibility for testing and verifying implementation updates from versions 0.4.5-0.4.10, including checks against agreed requirements, regression checks and retesting after fixes. Managed GitHub releases, coordinated presentation preparation and timing, and reviewed the overall flow of slides and scripts and their focus on software engineering concepts. |
| **Li Xiaxi** | 13763968 | Prepared the Requirements Engineering section, covering user needs and the system's main requirements. Participated in early use-case and workflow discussions and contributed feedback during the user trials. Also proposed distributing VoteLab as a downloadable ZIP package that users could extract and launch by double-clicking a startup file. |
| **Lu Ruilin** | 13749163 | Contributed to basic page sketches and layout suggestions for the initial prototype. Shared responsibility for the diagram-related work with Ge Yiwen and Hong Yan Wa, including flowcharts, sequence diagrams and activity diagrams. Prepared the corresponding presentation material to explain system processes and interactions, and participated in early user trials. |
| **Ge Yiwen** | 13695236 | Participated in initial database planning and technical research. Shared responsibility for system diagrams with Lu Ruilin and Hong Yan Wa. Contributed to the modelling section of the presentation, using process and interaction models to explain how the system works. Also participated in early user trials and improvement discussions. |
| **Hong Yan Wa** | 13886458 | Contributed to basic page sketches and layout suggestions for the initial prototype. Worked with Lu Ruilin and Ge Yiwen on the diagram-related section. Helped prepare the modelling slides that explained workflows, interactions and activity paths. Also tried the early application from a user's perspective and contributed improvement suggestions. |
| **Luo Jiayi** | 13782344 | Participated in early use-case and workflow discussions and contributed feedback during user trials. Prepared the Testing section with Zhao Yang, organising presentation material around how the application was checked. This section covered testing scenarios and the application's behaviour under normal and exceptional conditions. |
| **Zhao Yang** | 13792061 | Participated in initial database planning and technical research, as well as early user trials and improvement discussions. Prepared the Testing section with Luo Jiayi, helping organise the testing material and explain the checks used in the project. The presentation connected testing activities with the system's expected behaviour. |
| **Xia Weiyi** | 13744585 | Participated in early use-case analysis, basic flow diagrams and discussion of exceptional situations. Contributed feedback during the early user trials. Prepared the Validation section, focusing on whether the application met its intended user needs and requirements, and connected this discussion with the team's trial feedback. |

AI tools were used to assist with problem analysis, coding, translation and English editing.

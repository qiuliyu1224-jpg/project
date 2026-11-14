# VoteLab 0.4.5 - Repeated-launch recovery

本轮问题已从组员提供的终端错误和浏览器检查得到确认：Mac 上旧 VoteLab 已在后台运行，重复启动时默认 8765 端口产生 `Address already in use`；直接打开 http://127.0.0.1:8765/ 可以看到 VoteLab。

- 同一用户数据目录使用操作系统文件锁，避免两个新版启动器同时初始化同一个数据库；进程结束后操作系统释放锁。
- 0.4.5 重复启动先核对本地实例令牌，再打开已运行实例的同一地址。仅看到 VoteLab 字样不足以判断服务身份。
- 旧版 0.4.4 没有新版实例身份接口。升级前应先退出已知旧 VoteLab。无法确认身份的端口占用会明确报错，不自动换端口或停止其他程序，且在数据库备份和迁移之前停止。
- 启动日志始终写入原用户数据目录的 launcher.log，记录可进入 Python 阶段的启动错误；Mac 打包程序同时显示启动失败说明。Python 运行前的系统拦截或加载失败仍可能早于日志创建。
- Windows 使用独占端口绑定，避免复用已被其他 HTTP 程序占用的地址。原有 SQLite 数据位置、升级前备份和投票功能继续保留。

This release addresses the confirmed Mac error when opening VoteLab again while its local server is already running. A per-data-directory OS lock prevents a second new launcher from initializing the same database. Authenticated local instance discovery reopens the existing page. Unknown port occupants and legacy instances without the new identity endpoint produce clear guidance before database backup or migration. There is no automatic port switch or process termination.

Startup logging is independent of console availability. The packaged Mac app displays Python-stage startup failures. Windows uses exclusive port binding. Existing user data paths and SQLite startup backups are retained. Closing a browser tab still does not stop the app.

Validation required before publication: the full regression suite, process-level duplicate-launch/occupied-port/restart tests on native platforms, and duplicate-launch plus persistence checks using the actual extracted archives. Build checks run on macOS 15 for Apple Silicon and Intel; these do not claim a Finder GUI test, native macOS 14.5 validation, Apple notarization or production certification.

Before updating, quit the known older VoteLab process. Do not delete voting.sqlite3 or its backups. If the old app is already working, continue at http://127.0.0.1:8765/ until ready to update.

## Previous release notes

# VoteLab 0.4.4 - Third trial feedback

本版落实8项试用反馈：最终轮次结束后按公开/仅自己设置自动处理结果；新增柱状、横向柱状和折线统计图；新浏览器默认英文；邀请码页和创建页有返回入口；可切换账号；英文显示通过在线服务翻译中文活动内容；多数决选隐藏数量框；活动模板采用正式文案。

- 不重建或清空数据库。继续读取原用户数据目录，启动前保留SQLite备份。旧活动不擅自改成自动公开；创建者编辑并保存后使用新设置。
- 统计图读取同一份计票结果，不能绕过邀请码、结果发布和私密权限。评分仍为0-5平均分，未评分不当0分，显示人数；RCV可查看具体计票步骤，已淘汰项不伪装成零票。
- 多数决选第一轮需要决选时不提前发布最终结果；平票、无票均显示明确状态，不擅自选赢家。
- 在线翻译只改变显示，不改原文、编辑框或选票；有缓存、超时、限额和英文失败提示。MyMemory为外部服务，可能译错或不可用，匿名每日5000字符。账号身份、密码、手机号、邀请码、图片和选票不提交翻译。
- 切换账号仅撤销当前会话，旧账号数据及其他设备会话保留。多数决选后台继续限制每轮一项。

Addresses all eight trial items: automatic final-result publication or creator-only access, selectable charts, English default, return links, account switching, online English display translations, method-specific limits and formal template wording.

Existing data storage and startup backups are preserved. New PUBLIC events opt into automatic publication; untouched legacy settings remain manual. A majority round requiring a runoff is not published as the final result. Private and invitation-gated charts use the same permissions as the result table. Chart selection never changes votes.

Chinese visible activity text is translated through MyMemory (online, bounded timeouts, local cache, 5000-character daily anonymous allowance). Original records and editor fields remain intact. Source text is sent to an external service; use fictional non-sensitive activity content. Failure is labelled, with optional original-text viewing. No real SMS or permanent shared hosting is introduced.

Validation: regression tests plus isolated headless-browser checks for the eight changes, chart rendering, account switching, mobile layout and a synthetic live translation. Platform builds and package-restart persistence checks must pass before publication.

Reference: [MyMemory API](https://mymemory.translated.net/doc/spec.php), [usage limits](https://mymemory.translated.net/doc/usagelimits.php).

## Previous release notes

# VoteLab 0.4.3

修复多数决选仍显示“每人最多选几项”的问题。数量设置现在仅适用于单／多选。多数决选明确说明每人每轮选1个作品，第一轮无人过半时由前两名进入第二轮重新投票。评分和RCV也会隐藏无关的数量设置。旧活动和选票可继续使用。

Fixes the selection-limit field appearing for majority runoff. Only single/multiple choice uses the configurable limit. Majority runoff explains one choice per voter per round and a fresh top-two vote when nobody has a majority. Rating and RCV forms hide the irrelevant limit as well. Existing activities and ballots are retained.

## Included from 0.4.2

本版修复注册和密码页面的试用问题，并整理首页展示及输入提示。提供 Windows x64、Mac Apple Silicon 和 Mac Intel 安装包，运行环境包含在包内。

- 获取验证码改为在当前页面完成。请求期间保留国家／地区、手机号、称呼及密码输入，显示请求状态和返回结果。
- “显示密码”保留清楚标签，默认关闭，可按需要勾选。注册和重置密码的输入说明一致。
- 输入长度与后端检查一致。密码8～128个字符，注册和重置时两次输入须相同。称呼最多60个字符，手机号按所选国家／地区规则检查。
- 首页示例使用明确标注的界面演示图，真实活动、选票和结果继续读取实际数据库。
- 活动名称、作品名称和介绍使用中性的表单提示语，方便不同主题的活动使用。
- 更新继续使用原来的用户数据目录。已有数据库启动前生成经过完整性检查的 SQLite 快照，包含账号、活动、图片及选票记录。

注册和重置仍使用页面显示的演示验证码。共享投票需要所有人访问组织者提供的同一在线网址，各自运行的本地包分别保存资料。Mac 原生构建检查在 macOS 15 上进行，Mac 包未经过 Apple Developer ID 签名和公证。首次运行指引见包内 READ ME FIRST.txt。

VoteLab 0.4.2 addresses registration and password-page feedback and improves homepage examples and form guidance. Downloads include their runtime for Windows x64, Mac Apple Silicon and Mac Intel.

- Verification-code requests complete on the current page, preserve form entries and show request feedback.
- Show password has a clear label, remains optional and starts unchecked.
- Passwords allow 8–128 characters. Registration and reset require two matching entries. Display names allow up to 60 characters. Phone numbers follow the selected region's rules.
- Homepage examples are labelled interface illustrations. Actual activities, ballots and results use saved database records.
- Activity, entry and description fields use neutral prompts suited to different event topics.
- Updates reuse the existing user data directory. Startup snapshots of an existing SQLite database are integrity-checked and retain its accounts, activities, images and ballots.

Verification codes are local demonstrations displayed on screen. Shared voting uses one organiser-provided online URL. Local packages have separate data. Native Mac build checks run on macOS 15. The Mac app has no Apple Developer ID signature or notarization. The included READ ME FIRST.txt covers first-run instructions.


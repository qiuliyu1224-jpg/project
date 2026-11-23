# VoteLab 0.4.8 — Interface and guided workflows

- Warm ivory/walnut UI, local voting illustrations and large photographic covers.
- General-purpose homepage retains the original headlines and three example types.
- Two 5-step guides point to real controls and continue across page navigation.
- 600ms star feedback; final submit shrinks for 300ms, loads, then shows success
  only after a confirmed save. Reduced-motion preferences are respected.
- Ended events use a small acknowledgement dialog; transactional checks remain.
- Project-local Playwright and FFmpeg, pinned dependencies, runnable UI acceptance
  and recording scripts. These developer tools are not required by app users.
- Existing local data, backups, exports, restore and revote workflows are retained.

Upgrade: quit the older VoteLab background process, extract this ZIP, then launch.
Keep your user data folder. See docs/VERSION_048.md for details and boundaries.

---

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

---

# VoteLab / COMP3500

## 0.4.6 英文启动入口 / English desktop entry

双击首次启动或重复打开程序时，会明确进入英文首页，解决旧版 `lang=zh` 偏好导致仍显示中文的问题。进入后仍可在顶栏切换中文，普通页面导航保留当前选择。侧栏显示完整版本号。账号、活动、图片和选票不清除；旧数据目录及启动备份机制保持不变。启动器不再将旧版本实例误当作新版：升级前请退出已知旧 VoteLab，再打开新版。

Desktop launches explicitly open English even when the browser retains an earlier Chinese preference. You can still choose Chinese afterward. The sidebar shows the exact version. Older running versions are not silently reused. See [VERSION_046](docs/VERSION_046.md) for the eight-item acceptance checklist and limits.

## 0.4.5 重复启动处理 / Repeated-launch recovery

组员的 Mac 报错已确认是旧服务占用默认 8765 端口；浏览器打开 http://127.0.0.1:8765/ 可继续使用。关闭网页不会停止服务。更新前应先在活动监视器退出已知旧 VoteLab，保留原数据库和备份。

新版通过同一数据目录的操作系统锁和本地实例身份校验，重复启动时打开已经运行的 0.4.5 页面，避免再次初始化数据库。无法确认身份的端口占用会显示错误，不停止其他程序，也不悄悄换端口再启动。启动日志写入同一数据目录的 launcher.log；打包的 Mac 程序会显示 Python 阶段启动失败说明。Windows 采用独占端口绑定。说明和验证范围见 [VERSION_045](docs/VERSION_045.md)。

Version 0.4.5 reopens an authenticated running instance for the same data directory. OS locking prevents duplicate database initialization. Unknown port occupants are reported before database work; startup failures are logged even without a console. Quit an older VoteLab before upgrading. Local data storage and the existing voting features are retained.

## 0.4.4 第三轮试用反馈 / Third-trial feedback

新浏览器默认英文，保留已有语言偏好。顶栏支持切换账号，仅结束当前会话，不删除原账号资料。创建页和邀请码页有明确返回入口，模板采用正式名称。

创建时可选择结束后自动公开结果或仅自己查看。旧活动保留原来的手动发布设置，编辑保存后才按新选择执行。多数决选需要第二轮时不提前发布最终结果。后台截止处理需要程序保持运行；重启后也会检查已过期活动。

结果页默认显示票数／平均评分，按需生成柱状、横向柱状或折线图。评分轴固定0～5并显示人数；RCV可选择计票步骤。折线表示作品类别比较，不代表时间趋势，未评分或已淘汰项不会被补成零。

英文页面的中文活动文本通过MyMemory在线翻译，只改变显示，原文、编辑框和选票不改写。提供缓存、短期签名请求、超时和明确失败状态。翻译可能不准确，匿名服务每天限5000字符；离线时仅已有缓存可用。身份信息、密码、手机号、邀请码及选票不送往翻译服务。参考文档与8项验收见 [VERSION_044](docs/VERSION_044.md)。

New browsers default to English. Account switching preserves stored records. New PUBLIC events automatically publish at the end of the final voting round; private results remain creator-only, and legacy publication choices are preserved until explicitly edited. Result charts share the result page's access controls. Chinese activity text can be translated online by MyMemory for English display; originals and form values are unchanged. Network availability, translation quality and provider limits apply.

第四版：根据组员试用反馈改进的Python + SQLite课程原型。支持单／多选、多数决选、RCV、0～5星评分，中英文界面、作品报名审核及轮次历史。AI辅助实现，组员需要理解、复核和继续开发。

## 启动

Python 3.11或更新版本，在本目录运行：

```text
python -m pip install -r requirements.txt
python app.py
```

打开 http://127.0.0.1:8000 。这只属于运行程序的电脑；GitHub保存代码，不直接运行本程序。临时共享依赖电脑、网络及隧道，不是永久部署。

## 使用流程

- 账号：选择国家区号、输入手机号；注册需演示验证码、两次一致的8～128字符密码。登录使用密码，支持显示／隐藏；忘记密码用验证码重置，成功后旧会话失效。旧版验证码账号可通过重置入口设置密码。
- 一个账号可以创建、报名和投票，只能管理自己创建的活动。
- **验证码显示在页面，未发送短信，不证明号码归属。请用虚构资料和专用测试密码。**
- 创建：设置方式、单／多选上限、截止时间、结果权限、可选邀请码及标签，添加作品后保存预览，再确认开始投票或开放报名。
- 报名：名称／介绍／可选图片 → 待审核 → 创建者通过或说明原因驳回 → 参赛者报名期间可修改重交。待审／已审分栏，至少两项通过且无待审才可开票。
- 搜索：活动编号如V000005，支持名称、编号及标签。邀请码限制活动内容、图片、投票及结果访问，但不等于学校身份验证。

## 投票规则

| 方式 | 输入与计票 |
| --- | --- |
| 单／多选 | 最多选N个不同作品，每个被选作品加1票；N=1为单选。 |
| 多数决选 | 每轮选1项；超过有效票50%获胜，否则前两名第二轮重新投票；入围边界或最终平票时显示待处理。 |
| RCV | 可排部分作品，从1开始、不重复、不跳号。计最高仍有效偏好，超过当前有效偏好票一半获胜；淘汰唯一最低者后转票。最低票并列时停止，不随机淘汰。 |
| 星级评分 | 新活动可只评部分作品，至少评1项；0分有效，未评不当0分。按平均分排名，同时显示评分人数。 |

旧评分活动保留全部必评规则，避免默默改变已开始活动的含义；改变旧版评分规则需新轮次。平均分采用未舍入数值排序，界面两位小数；无评分显示“未评分”。评分人数不一致可能影响结果解读，因此显示人数，尚未设置未经确认的最低人数门槛。

核对不保存选票；最终提交在事务内检查截止、暂停、轮次、重复及作品归属。每账号每轮一次，失败不生成部分选票，旧确认页不能提交新轮次。

## 截止与修改

- 截止时间采用UTC+8，后台每5秒检查、每次请求及提交也检查；活动页每10秒检查状态，截止附近主动刷新，无需手动关票。
- 开票后创建者可暂停，最多成功保存3次修改，每次须公告。暂停期间不能投票，确认后恢复；修改记录可查。
- 只改文字、标签或延长时间保留票；替换图片、增删作品或改变旧必评规则则开新轮，旧快照与旧票保留，不混入新结果。投票方式、最多可选数量仍锁定。
- 创建者不能代写参赛者内容，但暂停时可移出名单并开新轮。已截止活动不能借此重新开放。
- 新建公开活动结束后自动发布；旧版活动按原手动发布设置处理。私密结果仅创建者可看。只显示汇总，不公开谁投给谁，但数据库内部有关联，不是密码学匿名。

## 验证及限制

```text
python -m unittest -v
```

测试用临时数据库，不改演示资料。用户截图逐项处理与验收见[VERSION_4](docs/VERSION_4.md)，参考网站见[REFERENCES](docs/REFERENCES.md)。旧版文档只作历史记录。

图片JPEG/PNG/WebP，5MB以内、最多1600万像素，重编码去元数据。无图或网络加载失败有反馈。20作品、截止30天及区号列表是演示边界，可由小组继续评估。

密码／邀请码PBKDF2加盐保存，登录和邀请码有尝试上限；仍未完成真实短信、机构核验、全站管理员、完整奖项名额分配、平票加赛联合审批、PDF导出、永久部署、生产安全审计和容量压测。平票暂停状态不等于已经实现后续处理工作流。

主要代码：app.py入口迁移；web4.py路由；ui4.py复用ui3.py布局；voting_rules.py选票计票；lifecycle.py修改和决选；entries.py图片作品；auth.py演示验证码；maintenance.py后台截止；demo_server.py小型并发服务。

SQLite账号、图片和选票保存在data/，不要提交数据库、运行日志或真实密码。原有其他课程文件不受修改。

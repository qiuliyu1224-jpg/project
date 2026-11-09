# VoteLab 0.4.2

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

# VoteLab 0.4.8 — Warm interface, guidance and feedback

## 用户使用 / Using this version

- 保留“发现值得支持的想法”“先看清楚，再做选择。”等原有文案。
  首页提供“作品评选／方案投票／项目展示”三类演示卡片，均明确标注为示例。
  示例不会创建数据库活动，也不会产生虚构选票。
- 奶油暖白、深棕文字和细线图标贯穿首页、账号页、活动与结果页。
  本地投票箱插画和大幅4:3图片不依赖图片网站。作品原图采用完整适配，不裁掉内容。
- 顶栏“操作指南”以及首页“5步操作指南”可随时打开。
  参与者：登录 → 找到活动 → 选择／评分／排序 → 核对并确认 → 检查保存与结果。
  创建者：登录 → 设置规则 → 添加作品并预览 → 检查并开票 → 管理与查看结果。
  指南跨页面继续，可关闭、后退、重新选择目标；不会自动创建活动或替用户投票。
- 星级选择有约600ms回弹、变色、8个小粒子和评分数字滚动。
  不增加点赞或虚构票数；0分和跳过仍保持不同含义。
- 最终提交按钮约300ms收缩为加载圆，实际保存成功后才显示绿色勾选，再恢复并进入活动页。
  失败恢复按钮；结果无法确认时引导先检查“我的投票”，不自动重试。
- 活动已经结束时点击提交，出现简短“知道了”弹窗。后端仍会在事务中重新校验，
  因而前端状态检查与实际提交之间发生的截止也不会产生过期选票。
- 系统“减少动态效果”偏好会关闭粒子和缩短动画。指南、提示框、按钮保留键盘操作。
- 仍为本地课堂原型；各电脑数据独立，验证码为演示用途。

## Upgrade

Quit the older VoteLab using **Local data & upgrades → Quit VoteLab safely**,
extract the new ZIP and launch it. Keep the existing user data folder. Startup
backup, restore, aggregate exports and explicit revotes from 0.4.7 remain available.

## Developer dependencies

Node.js tooling is separate from the Python application runtime. End users do
not need Node.js, Playwright or FFmpeg to run the downloaded VoteLab package.

From the repository root:

```text
npm ci
npm run browser:install
npm run tools:check
npm run test:ui
npm run video:encode -- input.webm output.mp4
```

`playwright` and `ffmpeg-static` are exact-pinned in package.json/package-lock.json.
The browser installer puts Chromium inside node_modules/.cache/ms-playwright.
FFmpeg is project-local via ffmpeg-static, not a system PATH modification.
Its upstream binary licence/provenance is retained by the installed package.

If the fixture cannot find Python, set VOTELAB_PYTHON to a Python executable with
voting-system/requirements.txt installed. Browser tests create a fresh disposable
database below ignored test-results; they never open the desktop user's database.
UI screenshots, a WebM recording, an FFmpeg-encoded MP4 and check results are saved
there. Fixture cookies and databases must stay ignored and must not be published.

## Artwork

The two voting illustrations and three editorial cover images were generated
with the built-in image_gen tool for this project. Exact generation prompts are
in static/assets/ASSET_PROMPTS.json. WebP versions retain transparency where
applicable and are encoded locally for a smaller offline package. Functional
outline icons are local SVG markup in ui_icons.py. No remote fonts or image hosts
are required.

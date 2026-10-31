# Version 2: review notes / 第二版更新

## Implemented

- 活动广场、管理工作台、状态筛选、标题搜索和响应式作品卡片。
- MANAGER / VOTER持久化角色。管理者仅管理自己的活动；投票者不能创建活动；登录页切换标签不能改变账号权限。管理者不能用管理账号投票。
- 显示/隐藏密码；独立的密码登录和验证码登录流程。
- 注册要求本地演示验证码。验证码5分钟有效、60秒获取间隔、最多5次错误尝试、单次使用，绑定浏览器和用途；不证明手机归属。
- 草稿保存、编辑、预览、确认发布；发布后锁定规则。
- 投票前核对页，未确认不保存；最终提交再次检查截止和重复。
- 星星1–5分与显式零分、汇总条形图、我的投票页面。

## Local SMS simulation is not real phone verification

没有连接短信服务，也没有发送短信。获取验证码后在页面上显示本地模拟码，明确标记LOCAL CODE。用于演示流程、过期、尝试限制和一次性使用。真实短信需要选定服务商、费用和服务端密钥；不得把当前流程写成已完成手机号实名认证或真实短信验证。

## Role boundary

管理者是本活动的组织者，不是全站超级管理员。课堂演示允许注册管理者账号，正式部署时的管理者邀请/审核政策仍需组内决定。管理员与创建者双人审批、全站审核、成员名单验证尚未实现。

## Remaining backlog

奖项自定义人数和自动分配、平票加赛/双人审批、延期审批、真实短信、机构编号验证、定时开始、后台定时任务、PDF导出、多选、多数决选、RCV、生产部署与性能测试仍未完成。

## Reference and adaptation

Reference: https://awardforce.com/features/judging-suite-features/voting-software/

Borrowed ideas: browsable entries, explicit voting rules, authenticated participation and separate management. This is our own local teaching implementation, not a copy of its commercial service. Guest visitors can browse open/closed event pages but cannot vote. The agreed once-per-round rule is retained. Award Force's social promotion, paid services, VIP/public mixed judging and integrations were not added to scope.

## Verification

19 automated tests cover the prior ballot and access rules plus role enforcement, wrong-role login, demo-code registration/login/cooldown/expiry/attempt limit/browser binding, editable drafts with post-publication locking, confirmation without saving, and static UI assets. Browser checks additionally verify the rendered page, password toggle, login and workflow. Report the actual executed test result rather than claiming all backlog requirements pass.

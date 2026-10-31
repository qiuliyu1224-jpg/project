# 2026-11-01：第一轮实现进度 / Increment 1

## 可用于logbook的事实

目前已从需求和设计进入基础实现阶段。首轮范围收窄为单选和0–5评分，先验证完整投票流程，再增加其他方式。此次代码为AI辅助产生的基础版本，需由全组复核、理解并继续开发，不应把它描述为组员各自独立完成的代码。

已实现：演示账号注册和登录、创建活动、草稿预览、手动确认开启、单选、每位候选人0–5评分、同一轮防重复、提交事务、截止检查、关闭、创建者查看结果、公开结果发布、私人结果限制、汇总条形图。

自动测试：2026-11-01在当前本地环境运行 `python -m unittest -v`，12项测试全部通过。涵盖预览不计票、单选与重复票、外部候选人、评分漏填和范围、截止、发布及隐私、操作权限、CSRF、失败回滚、转义及登录。测试不等于生产安全评审，也不是所有需求均已完成。

未完成：管理员角色、候选人审核、草稿编辑、独立确认页、手机号验证码、学号/工号核验、未来定时开始、后台定时任务、奖项分配、平票加赛审批、延期、PDF导出、联网部署、并发与性能测试。

部分实现：预览可查看但不能返回编辑已有草稿；截止在请求时更新并强制拒绝过期票，不是后台定时任务；身份仅为手机号格式的账号，不验证本人；私人结果只支持创建者，不含尚未实现的管理员。结果发布暂由创建者操作，这是供会议核对的原型选择，不能称为全组最终权限决定。

## English entry for adaptation

We moved from requirements and design into an initial implementation. We limited the first increment to single-choice and 0–5 score voting so that we could check a complete voting flow before adding more methods. An AI-assisted starter prototype now connects the pages, application logic and SQLite storage. It includes draft preview, per-round duplicate checks, atomic ballot saving, deadline checks and aggregate results with access controls. Twelve local automated tests passed on 1 November 2026. The team still needs to review the implementation and validate it against our agreed requirements. Administrator approval, award allocation, tie handling, verified identities and PDF export remain unfinished. We will treat these as backlog items rather than report them as completed work.

## Next meeting: 35 minutes

1. 5 min：全组运行并确认首轮范围为单选、评分；其他需求保留在backlog。
2. 10 min：演示创建、预览、投票、防重复、关闭、发布；一个人按正常情况操作，一个人尝试漏填/越权。
3. 10 min：确认框架选择和数据模型。当前使用Python标准库+SQLite以免安装依赖；这是可替换的演示实现，不是冒充已经确定的Django方案。
4. 5 min：优先决定下一轮草稿编辑、管理员权限、身份核验、奖项及平票的实现顺序。
5. 5 min：分配负责人、交付物和实际完成时间；记录缺陷和验收方式。

## Proposed implementation assignments (not completed work)

- A1：解释schema及轮次唯一约束，复核账户和选票的关联边界，更新ER模型。
- A2：审查技术选型、启动说明和依赖；统一全组运行环境。
- A3：审查单选/评分计票，补奖项和平票算法的明确样例。
- B1：创建、草稿编辑和预览页面。
- B2：评分、零分、漏填、提交成功与失败提示；增加独立确认页。
- B3：页面衔接、权限状态和结果显示；之后对接PDF导出。
- C1：用例与权限对照，检查原型和需求差异。
- C2：用真实输入走图、补异常测试，整理缺陷并复测。

11月17日是截图所示的10分钟进度展示，不是已确认的最终提交日期。演示PPT至少提前24小时交；具体课堂时间和其他截止时间以课程平台为准。

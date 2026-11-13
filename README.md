# WeChat-AI-Skills

**悦榕私域智能系统 · 客户 Agent 的上岗与运营技能库**

本仓库是 WeChat-AI-Skills 的唯一正式维护与发布入口，后续由 Codex 统一迭代。客户安装请使用[正式版本发布页](https://github.com/WeChat-AI-Skills/private-domain-ai-skills/releases/latest)中的固定版本。

让客户自己的 Agent 理解业务、学会运营方法，并在客户授权的系统中执行任务、核对结果。负责人定目标和规则，Agent 完成准备、执行与交接，复盘再改进下一轮工作。

![悦榕私域智能系统](assets/cover-v2.jpg)

**当前版本：v1.1.1 · 2026-11-13**。包含 15 项技能、安装程序、客户上岗模板和合成示例。首个适配宿主为 Codex；安装与识别、客户系统接入、业务执行分别验收，详见[能力状态](docs/capability-status.md)。

## 给客户的开始方式

把本仓库链接交给客户自己的 Agent，并附上这段话（Codex 已验证，其他宿主需核对技能目录和识别结果）：

> 请从 https://github.com/WeChat-AI-Skills/private-domain-ai-skills 阅读 README 和 docs/quickstart.md，安装 v1.1.1 的完整技能包。保留我已有的技能和配置，核对 15 项技能能否被识别。然后用 wechat-scrm-onboarding 检查我提供的 SCRM 入口、账号、业务资料和权限。本次先做只读上岗检查，告诉我能做什么、还缺什么，以及如何完成第一个任务。

[安装与首次上岗](docs/quickstart.md) · [客户环境卡](.agents/skills/wechat-scrm-onboarding/references/customer-setup.md) · [版本记录](CHANGELOG.md)

本仓库公开提供技能包，浏览、下载和克隆无需 GitHub 登录或单独申请访问权限。客户的 SCRM 账号、业务资料、工具连接和模型服务在各自环境中配置。

## 三条典型工作链路

| 客户任务 | 技能如何衔接 | 结果如何核对 |
| --- | --- | --- |
| 客户咨询后继续跟进 | 识别需求 → 档案草稿 → 跟进计划 → 授权发送 | 原账号、稳定客户、内容版本、出站记录 |
| 排一周朋友圈 | 营销目标 → 图文与素材 → 整批确认 → SCRM 排期 | 已保存、已发布、客户可见分别核对 |
| 活动邀请与群衔接 | 筛选去重 → 分层邀约 → 客户同意 → 群邀请 | 已邀约、同意、入群、订单分别记录 |

没有工具连接时，可先用授权资料生成草稿、计划和变更建议。实际提交需要在客户环境核实入口、对象、权限与授权。

## 技能清单

### 业务判断与编排

| 技能 | 用途 |
| --- | --- |
| [private-domain-ops](.agents/skills/private-domain-ops/SKILL.md) | 运营总控：选择技能，衔接任务与回执 |
| [customer-intake](.agents/skills/customer-intake/SKILL.md) | 咨询接待、需求识别、答复草稿 |
| [customer-profile](.agents/skills/customer-profile/SKILL.md) | 档案、标签、分层与变更 diff |
| [followup-plan](.agents/skills/followup-plan/SKILL.md) | 跟进理由、计划、频次与停止条件 |
| [moments-calendar](.agents/skills/moments-calendar/SKILL.md) | 朋友圈文案、素材需求和排期方案 |
| [campaign-invite](.agents/skills/campaign-invite/SKILL.md) | 活动筛选、分层文案、群议程与漏斗 |
| [sales-review](.agents/skills/sales-review/SKILL.md) | 执行复盘、规则候选、版本与回滚条件 |

### 系统操作与配套核验

| 技能 | 用途 |
| --- | --- |
| [task-reconcile](.agents/skills/task-reconcile/SKILL.md) | 原任务查询、逐对象状态与部分完成核对 |
| [wechat-scrm-onboarding](.agents/skills/wechat-scrm-onboarding/SKILL.md) | 首次核对企业、账号、权限和可用入口 |
| [wechat-scrm-moments](.agents/skills/wechat-scrm-moments/SKILL.md) | 朋友圈图文排期、原地修改、结果回读 |
| [wechat-scrm-friend-message](.agents/skills/wechat-scrm-friend-message/SKILL.md) | 指定好友或名单的消息准备、提交与核验 |
| [wechat-scrm-group-invite](.agents/skills/wechat-scrm-group-invite/SKILL.md) | 现有客户群邀请及成员状态核对 |
| [wechat-scrm-friend-cleanup](.agents/skills/wechat-scrm-friend-cleanup/SKILL.md) | 关系复核及按具体授权执行的清理 |
| [wechat-activity-customer-handoff](.agents/skills/wechat-activity-customer-handoff/SKILL.md) | 活动与礼赠答疑草稿、员工交接及回执 |
| [audit-youzan-cart-nonbuyers](.agents/skills/audit-youzan-cart-nonbuyers/SKILL.md) | 同窗口加购与已购客户去重、排除及对账 |

## 使用、反馈与迭代

使用 [合成示例](examples/README.md)检查需求识别、排期和名单核对，再在客户环境完成一个明确授权的小范围任务。真实客户资料、凭据与回执存于客户工作区。

反馈带上版本、使用场景、预期、实际结果及脱敏复现步骤。每次迭代更新 [CHANGELOG](CHANGELOG.md)、示例和[能力状态](docs/capability-status.md)，发布固定版本；安装副本按用户选择更新。

后续优先验证“上岗 → 朋友圈排期 → 实际结果”，再根据客户反馈改进接待、跟进、活动与复盘。工具服务端和商品上下架适配列为后续工作。

[能力目录与迭代路线](docs/iteration-roadmap.md) · [技能登记](manifest.json) · [运营方法](docs/method.md) · [授权规则](docs/boundaries.md) · [接入说明](docs/tool-contract.md) · [许可范围](NOTICE.md)

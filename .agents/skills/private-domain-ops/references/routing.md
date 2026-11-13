# 任务路由

明确任务可直接调用相应技能；多步骤任务按依赖关系推进，复用已有事实与授权。

| 目标 | 业务判断 | 执行与结果 |
| --- | --- | --- |
| 首次接入、环境变化 | [wechat-scrm-onboarding](../../wechat-scrm-onboarding/SKILL.md) | 只读核对能力与缺口 |
| 咨询与需求识别 | [customer-intake](../../customer-intake/SKILL.md) | 要发送时进入 [wechat-scrm-friend-message](../../wechat-scrm-friend-message/SKILL.md) |
| 档案、标签、分层 | [customer-profile](../../customer-profile/SKILL.md) | 已适配的档案入口；无入口交付 diff |
| 跟进计划 | [followup-plan](../../followup-plan/SKILL.md) | [wechat-scrm-friend-message](../../wechat-scrm-friend-message/SKILL.md) |
| 朋友圈内容与周排期 | [moments-calendar](../../moments-calendar/SKILL.md) | [wechat-scrm-moments](../../wechat-scrm-moments/SKILL.md) |
| 活动名单、文案与群议程 | [campaign-invite](../../campaign-invite/SKILL.md) | 好友消息 → [wechat-scrm-group-invite](../../wechat-scrm-group-invite/SKILL.md) |
| 活动/礼赠问题与员工换班 | [wechat-activity-customer-handoff](../../wechat-activity-customer-handoff/SKILL.md) | 人工渠道处理与回执 |
| 加购未购核验 | [audit-youzan-cart-nonbuyers](../../audit-youzan-cart-nonbuyers/SKILL.md) | 已授权且可对账的两份输入 |
| 关系核对或指定名单清理 | [wechat-scrm-friend-cleanup](../../wechat-scrm-friend-cleanup/SKILL.md) | 只核查或按具体删除授权执行 |
| 复盘与规则候选 | [sales-review](../../sales-review/SKILL.md) | 有写回权限和入口才更新系统 |

例如“排一周朋友圈并提交”：先生成有事实依据的最终图文与带时区排期，核对整批授权，再提交，最后查原任务。单纯“写文案”只交付草稿。

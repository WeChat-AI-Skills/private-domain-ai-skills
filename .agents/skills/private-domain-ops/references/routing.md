# 任务路由

明确任务可直接调用相应技能；多步骤任务按依赖关系推进，复用已有事实与授权。

产品目录按上岗与编排、客户意图判断、发朋友圈、一对一聊天、拉群、上架、复盘排序，见[技能树登记](catalog/skill-tree.json)。排序是导航，不是每个任务必须执行的步骤。manifest.json 的旧六域仅为登记协议 1.0 兼容分类。

总控先识别目标、执行模式和可用工具，再按[角色登记](catalog/agent-registry.json)读取所需角色。复杂任务使用[工作流模板](catalog/workflow-registry.json)与[任务卡](contracts/task-and-result.md)；草稿目标不进入 external 步骤。缺商品事实时给商品角色资料核对任务；商品上架本版本未交付，列出缺口，不调用不存在的 product-listing。

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
| 提交超时、部分完成、执行后核对 | [task-reconcile](../../task-reconcile/SKILL.md) | 只读查原任务，逐对象归类，未知不重发 |

例如“排一周朋友圈并提交”：先生成有事实依据的最终图文与带时区排期，核对整批授权，再提交，最后查原任务。单纯“写文案”只交付草稿。

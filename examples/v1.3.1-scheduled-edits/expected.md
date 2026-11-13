# 验收标准与范围

以 [统一规则第 5 条](../../.agents/skills/wechat-scrm-onboarding/references/operation-receipts.md#scheduled-task-changes) 为准；详细判据见 [rubric.json](rubric.json)。

1. G1：原 ID 修改并保存；保存响应后重开原任务，逐字段确认仅首图更换，账号、收件人或可见范围、时间及其他内容排版不变。
2. G2：无修改入口、修改失败或读回不一致时保留原任务并报告；保存未知先查原任务，不以取消重建、配置复制提交或重发替代内容修改。
3. G3：只有整批名单或发送账号更换且原任务不可修改，才向指定负责人报告原任务、变更范围和证据并等待决定。获准取消并重建后，仍须旧任务确已取消且未执行，才能进入替代任务流程。

独立复核见 [review.md](review.md) 与 [review.json](review.json)。任何“通过”只表示本次合成决策轨迹符合规则，不表示真实页面操作能力或业务验收。

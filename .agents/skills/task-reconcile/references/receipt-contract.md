# 结果契约 1.0

本契约定义归一化输入，不声称任何 SCRM 已实现这些字段。适配真实平台时必须记录字段映射和查询来源；不明字段保留未知。操作权限和客户联系意愿分别校验，不能相互替代。

```json
{
  "contract_version": "1.0",
  "mode": "simulation",
  "task_id": "synthetic-task-1",
  "tenant_id": "synthetic-tenant",
  "account_id": "synthetic-account",
  "operation": "message_send",
  "content_version": "v1",
  "expected_targets": ["synthetic-customer-1"],
  "items": [
    {"target_id": "synthetic-customer-1", "status": "pending", "stage": "accepted"}
  ]
}
```

- `mode` 为 offline、simulation 或 connected_readonly。核对真实写操作的结果属于 connected_readonly，不代表本技能执行写操作。
- `expected_targets` 必须来自原提交名单，唯一且非空。每个返回对象最多一条归一化记录；多个历史快照先按可信任务事件核对，无法消解时不自动取最新一条。
- 逐项记录继承外层企业、账号、任务、动作、内容版本、模式和契约版本；如果逐项再次提供这些字段，必须与外层一致，否则报错，不能带着矛盾上下文统计成功。
- `operation` 支持 message_send、moments_schedule、group_invite。成功阶段分别为 sent、published、invitation_sent。群成员、已读与成交是另外的业务指标。
- `status` 是 succeeded、failed、pending、unknown、cancelled、expired。pending 的 stage 是 accepted、scheduled、processing；unknown 的 stage 为 unknown；其余终态需与动作对应。
- 终态必须附 `evidence_ref` 和带时区的 `verified_at`。缺少证据字段降为 unknown。脚本不能验证证据是否真实；Agent 必须查询原系统并确认引用属于同一企业、账号、任务、对象和内容版本。
- 计数总和等于原名单数量。缺行记 unknown；重复、额外对象、非法状态或阶段直接报错。空名单不推断为“全部完成”。

## 模拟提交协议

`mock_scrm.py` 是故障测试夹具，输入只能为 simulation。命令包含 task_id、tenant_id、account_id、operation、targets、content、content_version、policy_version、idempotency_key、authorization_ref、evidence_refs。`command_hash()` 绑定全部命令字段，授权夹具必须提供同一个 authorized_command_hash、grant_id、expires_at 和 revoked=false。

这是对一份明确单次/批次命令的合成授权测试；不实现持续授权策略、客户营销意愿判断或真实身份鉴权。真实执行仍按[授权规则](../../private-domain-ops/references/authorization.md)复用已有有效授权，不能因模拟器字段有限强迫客户每次重新批准。

SQLite 对 `(tenant_id, account_id, operation, idempotency_key)` 保持唯一；同键不同载荷拒绝。受理事务提交后才模拟超时，重新打开数据库可按原键查询。幂等记录只代表这个模拟器，真实平台需有持久化记录、去重和查询契约。模拟器不代表跨平台 exactly-once 保证。

`--demo` 输出 10 个合成对象的 7 成功、2 失败、1 未知，并验证超时后查询未新增提交。数据库自动清理；无外部消息或 SCRM 写入。

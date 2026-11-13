# 工具契约（可选）

技能默认在**离线模式**下工作：读用户粘贴的对话与资料，输出可复制文本和执行清单。
如果宿主接入了系统工具（MCP），技能可以读取客户档案、生成草稿、提交发布任务。

本仓库**不包含**服务端实现。这里定义的是一份契约：工具叫什么、输入输出是什么、权限如何校验。接入方按自己的系统实现。

## 1. 先判断模式

技能开始时先确认：

| 检查 | 在线模式 | 离线模式 |
| --- | --- | --- |
| 是否有 `customers.get` 等工具 | 有 | 无 |
| 能否读到客户 ID | 能 | 不能，只用用户提供的信息 |
| 能否发送 | 看权限 | 不能，输出"待发送文本" |

**不得假装调用成功。** 没有工具就说"当前没有接口，我给出可复制版本"，绝不编造客户 ID、发送结果、打开率。

## 2. 工具清单

### 读

```text
customers.search(query, filters?) -> [{ id, name, stage, tags, last_touch_at }]
customers.get(id) -> { profile, recent_messages[], orders[], todos[] }
catalog.search(query, filters?) -> [{ sku, title, price, stock, attributes }]
metrics.query(from, to, dims[]) -> [{ dim, reach, reply, convert }]
```

### 写（需授权）

```text
customers.upsert_profile(id, patch, evidence) -> { ok, diff }
tags.apply(id, tags[], reason) -> { ok }
messages.draft(customer_id, intent, constraints) -> { draft_id, text }
messages.send(draft_id) -> { ok, sent_at }          # B 级
moments.schedule(posts[]) -> { ok, scheduled[] }     # B 级
campaigns.segment(rules) -> { segment_id, count }
campaigns.invite(segment_id, script, consent_required) -> { task_id }  # B 级
```

### 约束

- 每个写操作必须带 `evidence`（依据的消息 ID 或原话），否则拒绝；
- `messages.send`、`moments.schedule`、`campaigns.invite` 需要 B 级确认令牌；
- 工具返回失败时如实报告，不重试超过 2 次，不换路径绕过；
- 任何工具都不能替技能决定价格与折扣。

## 3. 最小实现建议

如果要做参考实现，优先这五个：

1. `customers.search` —— 没有它，技能只能处理单个客户；
2. `customers.get` —— 提供上下文，决定判断质量；
3. `customers.upsert_profile` —— 让结果沉淀，而不是聊完就丢；
4. `messages.draft` —— 把草稿与发送分离，天然形成确认点；
5. `metrics.query` —— 让复盘有数据，不靠感觉。

先做读、再做写；先做草稿、再做发送。发送权限最后开。

## 4. 权限模型

| 动作 | 需要的授权 |
| --- | --- |
| 读客户档案 | 该客户在服务范围内 |
| 写档案/标签 | A 级，可回滚 |
| 生成草稿 | A 级 |
| 发送单条 | B 级，逐次确认 |
| 批量邀约/发布 | B 级，按批次确认 |
| 改价/退款/删除数据 | C 级，仅人工 |

权限校验放在服务端，不放在提示词里。技能里的"不要发"是行为约束，不是安全边界。

## 5. 返回给技能的上下文格式

建议统一为：

```json
{
  "customer_id": "c_1024",
  "stage": "intent",
  "tags": ["品类:裤装", "偏好:宽松腰", "来源:直播"],
  "recent_messages": [
    { "at": "2026-11-12T23:48:00+08:00", "from": "customer", "text": "周末有个活动，预算 500 左右……" }
  ],
  "orders": [],
  "todos": ["确认收货城市"]
}
```

时间带时区；金额带币种；缺失字段用 `null`，不要用空字符串冒充"没有"。

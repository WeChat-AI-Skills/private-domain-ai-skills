# 档案结构与分层

下面是空白结构，null 表示未取得，空数组仅在已确认无记录时使用。模板不代表实际客户。

```yaml
customer_id: null
tenant_id: null
account_id: null
identity_status: pending
updated_at: null
owner: null
facts: []
inferences: []
pending_questions: []
budget:
  original_text: null
  amount: null
  currency: null
  precision: null
  hard_upper_bound: null
tags: []
legacy_stage: null
legacy_stage_evidence: null
lifecycle: null
intent: null
marketing_contact: null
engagement: null
service_status: null
purchase_history: null
evidence: []
proposed_changes: []
write_status: draft
```

每项事实、推断和标签关联来源引用、证据时间及适用范围。预算“500 左右”可记 amount=500、precision=approximate、hard_upper_bound=null，原话完整保留；“最多 500”才设置已确认币种下的 hard_upper_bound=500。

## 五个独立维度

企业已有字段优先，以下是归一化映射建议，不能据此自动修改客户数据库。

| 字段 | 表达什么 | 依据与限制 |
| --- | --- | --- |
| lifecycle | new、first_purchase、repeat_purchase、dormant 等关系生命周期 | 依据完整度足够的历史及企业口径；历史缺失不判新客 |
| intent | 当前目标商品/需求、意向级别、有效时间 | 历史购买不代表当前意向；high 需当前明确证据 |
| marketing_contact | 联系意愿记录列表，各自带 decision、scope、scope_id、channel、effective_at、expires_at、source_ref | decision 为 allowed、declined、unknown；scope 为 all_marketing、campaign、channel、product 等。未知不填 allowed |
| engagement | 最近一次互动时间、回复情况、渠道 | 不等于购买意向或营销同意；不能从单次未回复判流失 |
| service_status | 售后请求、工单状态、负责人 | 与营销拒联独立；不能把售后答复夹带营销 |

每个维度保留 evidence_ref、observed_at、适用对象；冲突未消解时保留两条。字段缺失为 null，不是 false 或 0。`marketing_contact` 已确认没有意愿记录时可为空列表，但仍不代表同意。

例如合成客户有两次已核实订单，今天又问同一商品如何付款：lifecycle=repeat_purchase，intent 可按当前证据记 high。客户说“这次活动不参加”：追加 scope=campaign、scope_id=该活动、decision=declined；其他活动许可仍按各自现有记录核实，不能自动填 allowed。

客户说“以后别再给我营销消息”且正在退货：all_marketing=declined，同时 service_status=售后处理中。停止营销，按服务请求与授权继续处理退货。

## 旧字段迁移

旧 `relationship_stage`、`stage` 和 `marketing_consent` 原值连同来源、时间保留在迁移草稿；无损映射到 legacy_stage/原始记录引用。只有“已购高意向”标签而没有订单或近期对话时，不直接生成复购、高意向或营销同意。提出待核字段及 diff，经授权才写入；本版本没有数据库自动迁移程序。

身份合并需要稳定对应证据。输出字段 diff 和冲突；写入前核对授权、原版本或更新时间，避免覆盖别人刚做的修改，写入后回读。

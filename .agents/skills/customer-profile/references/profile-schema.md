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
tags: []
relationship_stage: null
purchase_history: null
marketing_consent: null
evidence: []
proposed_changes: []
write_status: draft
```

每项事实、推断和标签关联来源引用、证据时间及适用范围。预算“500 左右”可记 amount=500、precision=approximate，原话完整保留；不能自动设置最高价。

分层规则应来自企业。参考顺序：先核对拒联/服务状态；购买历史中先判复购再判单次已购；结合有时间的购买意向证据评估当前跟进阶段。购买历史与当前意向可以并存。无足够记录时标待核，不默认高意向或新客。

身份合并需要稳定对应证据。输出字段 diff 和冲突；写入前核对授权、原版本或更新时间，避免覆盖别人刚做的修改，写入后回读。

# 规则卡

```yaml
rule_id: null
version: null
status: draft
owner: null
trigger: null
action: null
exceptions: []
evidence: []
counterexamples: []
applicable_scope: null
confidence_basis: null
observation_plan: null
metrics_definition: null
authorization_reference: null
effective_at: null
rollback_condition: null
previous_version: null
```

模板空值代表尚未填写。事实缺失时记录缺口，不能编造案例编号、样本量或效果。

- draft：假设或建议。
- shadow：观察判断，不下发业务动作；需要真实运行记录才能声称已开始。
- active：已批准并核实生效，动作仍受原权限和范围约束。
- deprecated：停止新调用，保留历史及替代规则。

状态变更记录批准人、版本、时间、范围和回读证据。规则不能覆盖拒联、身份核对、当前用户指令或系统权限。计划、批准、写入与生效分别判断。

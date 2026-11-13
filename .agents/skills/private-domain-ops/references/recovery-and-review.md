# 恢复、独立审查与签核记录

适用 task-card/1.2。这是离线文件契约，不是权限服务、身份鉴真或真实工具适配。检查器只读显式传入的任务、结果与证据包；不会打开记录中的文件、网址或任意引用，也不会提交业务动作。

## 何时需要完整记录

| 声明 | 所需记录 |
| --- | --- |
| L0 简单任务 | 不额外要求证据包，保留事实依据 |
| L1/L2 自审 | 原 A卷引用即可；实际判断责任不变 |
| 声明 independent 且已完成、已有新动作或检查执行就绪 | 独立审查记录 |
| L3 有新动作，或 readonly/execute 的 completed，或检查执行就绪 | 独立审查、恢复、签核三条记录 |
| 无新动作的 prepared、waiting_*、blocked、running、cancelled | 可缺少尚未形成的记录；明确缺口 |
| draft 草稿完成 | 可用 pending 表明待审；不代表业务执行完成 |

即使 L3 execute 的 action_refs 为空，completed 仍需三条记录。L3 readonly 使用同样的绑定规则，不能因没有业务写入而绕过审查。已部分执行而证据不全时，保留原动作、失败回执和事故记录；检查失败不能通过清空 action_refs、降风险或改为 draft 来消除。这个脚本不保存历史，也无法侦测已经被外部删除的记录。

## 任务绑定

任务的 evidence_subject 必须含 request_id、task_id、scope、execution_mode、operation、object_version、policy_version。前四项与任务完全一致。execute 还须分别匹配 action、content_version、policy_version；readonly 的 operation 是读取/导出目标，object_version 是资料快照或查询版本。对象、账号、范围、版本或用途改变，就要重新核对记录。

executor 使用 `{ "actor_id": "执行身份", "context_id": "执行上下文" }`。assigned_to 和 result.agent_id 是业务角色，不是执行身份。一个宿主可以扮演多个角色；改角色名称并不构成独立审查。

三个引用是证据包中的记录 ID，不是让检查器自动打开的路径：

| 任务字段 | 记录 kind |
| --- | --- |
| adversarial_review_ref（沿用原字段） | review |
| recovery_plan_ref | recovery |
| human_approval_ref | approval |

证据包格式为 `{ "schema_version": "evidence-bundle/1.0", "records": [...] }`。每条记录的 id 唯一，subject 必须与任务 evidence_subject 完全一致。只检查任务所引用的记录；包内未关联记录不能填补缺口。

## 三种记录

每条记录共有 id、kind、subject，另有：

- **review**：reviewer（actor_id、context_id）、artifact_ref、independence_basis、verdict（approved/rejected/pending）、unresolved_blockers 字符串列表、reviewed_at、valid_until。independent 模式要求声明的审查身份与上下文均不同于 executor；完成或就绪要求 approved 且无未解决阻断项。记录仍可能是伪造的，检查器不证明独立性真实发生。
- **recovery**：reversibility（reversible/irreversible/not_applicable）、rationale、owner、authority_boundary、verification，以及非空 stop_steps、remediation_steps 字符串列表。不可逆动作必须说明停止和补救；not_applicable 也需说明原因及实际停止/补救安排，不能填空字符串代替。检查器只检查这些说明的结构。
- **approval**：approved_by、status（approved/revoked/pending）、grant_type（single/batch/ongoing）、artifact_ref、approved_at、valid_until。完成或就绪要求 approved。已有整批/持续签核可复用，但本条记录必须绑定当前任务范围与最终版本；授权人的真实身份、原始授权覆盖范围由执行者核对。

时间均为带时区的 ISO 8601，valid_until 晚于 reviewed_at/approved_at。artifact_ref 只是可追溯位置，存在字符串不证明内容存在或有效。

## 三种检查，不混为授权

1. `--check-task TASK --result RESULT --evidence-bundle BUNDLE`：检查结构、记录齐全和关联，以及完成声明所需的裁决/签核状态。clock_mode 为 structure_only；不会按今天的时间让历史完成卡过期失读，也不宣称当前就绪。
2. 在上面加 `--replay-at 2026-11-13T12:00:00Z`：按明确声明的历史或合成时点检查有效期，clock_mode 为 declared_replay。仅接受 1.2 任务与显式证据包。该时点不是经鉴真的事件时间，不能证明当时实际授权。
3. `--check-task TASK --evidence-bundle BUNDLE --check-ready`：使用真实当前时钟检查所需记录的当前有效期，clock_mode 为 current。禁止同时提供 --result 或 --replay-at。拒绝 draft、待人工决定、待审或旧版卡片。

输出 current_evidence_ready 仅表示当前证据契约检查完成；authenticity 和 authorization 始终 not_verified。即使检查通过，真实权限、风险等级、业务连接、原系统状态和人员身份仍须由实际执行者核对。检查器不会派遣 Agent、执行恢复或批准发送。

## 合成演练

[合成任务](examples/evidence-task.json)、[合成结果](examples/evidence-result.json)、[证据包](examples/evidence-bundle.json)模拟 L3 只读任务，包含全部三类记录。它们没有客户数据，没有真实签核。安装后从总控技能目录运行：

```sh
python3 scripts/catalog.py --check-task references/examples/evidence-task.json --result references/examples/evidence-result.json --evidence-bundle references/examples/evidence-bundle.json --replay-at 2026-11-13T12:00:00Z
```

请保留旧卡和原始结果。1.0/1.1 继续按原语义读取；新执行需要复制成 1.2 并补齐真实记录，不可只改版本号。旧任务或结果混入 evidence_subject、executor 或 recovery_plan_ref 会报部分迁移，避免静默跳过新字段。

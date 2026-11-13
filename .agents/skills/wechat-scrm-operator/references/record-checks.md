# 客户绑定与记录检查

日常操作先按相应操作步骤完成实际观察，简单任务不要求客户手填整套 JSON。Agent 可以在客户受控工作区保存必要记录，并在需要跨步骤、恢复或交接时使用本契约。配置、会话和运行证据放在技能安装目录之外，升级时不会混入技能源文件。

## 文件用途

| 文件 | 用途 |
| --- | --- |
| [操作档案](scrm-profile.json) | 本包方法范围、菜单别名、字段和回读索引；不是客户已连接证明 |
| [客户绑定 schema](contracts/customer-binding.schema.json) | 约束客户入口、租户/工作号、宿主会话、适配版本和逐操作声明 |
| [调用 schema](contracts/capability-call.schema.json) | 固定本次能力/操作、调用身份、绑定、范围、最终内容及授权引用 |
| [结果 schema](contracts/capability-result.schema.json) | 保存与原调用严格对应的结果阶段、原系统证据与未核实项 |
| [未知状态绑定模板](examples/binding.example.json) | 新客户起点；未知字段必须用真实检查补齐，不能复制合成值当现场结论 |
| [合成绑定](examples/synthetic-binding.json)、[合成调用](examples/synthetic-call.json)、[合成结果](examples/synthetic-result.json) | 本地结构与关联演练；全部为合成输入，不可用于真实业务 |
| [合成查询调用](examples/synthetic-query-call.json)、[合成查询结果](examples/synthetic-query-result.json) | 显式带原调用和原结果，核对查询是否属于同一范围、实现和原平台记录 |

绑定中的操作 `unknown`、`supported`、`unsupported` 是所提供记录的声明，不是脚本联网探测结果。即使填写 `supported`，Agent 仍需实际读取当前页面、核对有效业务授权与操作条件。`checked_at` 和 `evidence_ref` 用于定位本地观察记录，检查器不会自动打开证据引用。

适配标识 `supplied-scrm-web` 和能力名 `moments.submit`、`messages.send`、`task.query` 是本包内部命名，不是厂商 API 地址。未来增加 API/MCP/CLI 路径需要真实工具文档、独立适配版本与验收，不能仅更改绑定里的 transport 就变成已接入。

## 本地命令

使用 Python 3.10+，在本技能目录执行。工具仅读取显式给出的本地 JSON，没有网络登录、发送、发布或平台查询功能。

```bash
python3 scripts/scrm.py list
python3 scripts/scrm.py check-binding references/examples/binding.example.json
python3 scripts/scrm.py check-binding references/examples/synthetic-binding.json
python3 scripts/scrm.py check-call references/examples/synthetic-call.json --binding references/examples/synthetic-binding.json
python3 scripts/scrm.py check-result references/examples/synthetic-result.json --call references/examples/synthetic-call.json --binding references/examples/synthetic-binding.json
python3 scripts/scrm.py check-result references/examples/synthetic-query-result.json --call references/examples/synthetic-query-call.json --binding references/examples/synthetic-binding.json --origin-call references/examples/synthetic-call.json --origin-result references/examples/synthetic-result.json
```

检查客户记录时，将示例路径替换为客户受控工作区内相应文件的实际路径。输出包含 `offline_only: true` 与 `live_status: not_verified`；`can_execute: false` 表示这个检查器不放行业务操作、不调用平台。客户 Agent 的实际页面操作仍须使用可用工具和有效授权。退出成功仅代表检查范围内的记录一致性；缺真实工具、过期权限、被撤销的授权或错误的网页证据不会因为 JSON 合法而变成可执行。

不要把密码、Cookie、验证码、访问令牌或完整认证配置写进绑定；使用宿主已有的受控登录。HTTP 入口只有客户明确允许的部署才使用，不能为让模板通过而自动降低传输要求。

## 调用、结果与原任务关联

使用示例/schema 中的 `subject` 关联结构，结果必须保留原调用的关联字段。关联内容包括请求/任务/调用/尝试、企业与工作号、绑定修订、能力/操作/版本、冻结实现、最终输入及授权依据。更换工作号、内容或实现后不能复用旧结果充当本次成功。

`subject.binding_digest` 绑定完整客户绑定快照；历史回执使用原快照核验，现场重新检查后另存新修订，不覆盖原快照来改变历史含义。`input_digest` 与 `idempotency_key` 使用 SHA-256：规范 JSON 为 `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)`，以 UTF-8 编码后计算。Agent 可复用脚本公开函数 `scrm.input_digest(value)` 与 `scrm.operation_fingerprint(subject)`，不用重新实现摘要算法。

指纹绑定 request/task、binding、租户/账号、operation、capability_version、object_version 和 input_digest，不因 attempt_id 改变就生成另一个同目标业务意图。它仅是本地防重依据，不能推导平台支持幂等；每次点击无需单独造调用记录，记录的是有业务效果的提交/查询。

异步查询要保留原提交的关联及本次查询依据。迟到结果归原尝试；平台任务 ID、观察时间和业务阶段需要原系统证据，不从本地 schema 或 HTTP 请求返回值推导。

`task_query` 的 `check-call` 与 `check-result` 都必须显式提供 `--origin-call`、`--origin-result`。检查器核对原调用/原结果彼此关联，以及租户、工作号、绑定快照、冻结实现、对象版本、原操作和原平台标识；只复制两个 origin ID 字符串不足以通过。原提交尚无平台标识时，先由宿主工具按原账号、时间、内容等证据找回唯一记录；未找回保留未知，本地脚本不会代替检索。查询完成可为 `succeeded/queried`，其中原业务仍可是 `accepted/scheduled`，不代表已发布。

外部图片、选项、消息内容和策略引用使用 `{ref, sha256, version}` 保存声明快照。`sha256` 是引用内容的 SHA-256 十六进制摘要；操作时应实际核对对应素材/配置版本。检查器只验证摘要格式及它是否被原输入摘要绑定，**不打开引用，不证明被引用内容或摘要真实**。引用所指内容改变必须产生新版本/摘要并重新检查最终任务。

新记录通过现有任务的证据/动作引用关联，不改变 `task-card/1.2` 的 `capability_ids`：该字段仍指业务节点。原 1.0/1.1 任务卡继续按旧语义读取；新执行的 A卷、风险、独立审查和签核要求见[现有任务结果约定](../../private-domain-ops/references/contracts/task-and-result.md)。本检查器不替代它。

现有[逐对象回执 1.0](../../task-reconcile/references/receipt-contract.md)仍用于相符的消息、朋友圈、邀请记录。只有真实字段与阶段满足时才映射；“排期已保存”“规则已开启”“页面按钮可点”都不能改写成业务成功。

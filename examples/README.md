# 示例

五个合成场景，用来演示输出格式，也可以当作评测用例：

| 示例 | 对应技能 | 看什么 |
| --- | --- | --- |
| [night-inquiry](night-inquiry/input.md) | `customer-intake` | 一句话拆需求、只问一个关键问题、不承诺时效 |
| [week-of-moments](week-of-moments/input.md) | `moments-calendar` | 把"别刷屏"变成规则、不补造商品事实、日期与时区正确 |
| [campaign-invite](campaign-invite/input.md) | `campaign-invite` | 交集不明保留未知、计划与执行分开 |
| [customer-state](customer-state/input.md) | `customer-profile` | 复购与当前意向并存、活动拒绝范围、拒营销与售后分开 |
| [task-results](task-results/input.md) | `task-reconcile` | 超时回查、7/2/1 结果、排期与发布分开 |

## 怎么用

1. 把 `input.md` 里的输入交给装好技能的模型；
2. 对照 `expected.md` 看结构是否齐全：已知/推断/待确认、授权级别、停止条件；
3. 不要求逐字一致——话术可以不同，但**判断与边界**必须一致。

## 评测时看什么

- 有没有把推断写成事实；
- 有没有在未确认时做出承诺；
- 有没有一次问太多问题；
- 有没有给出停止条件；
- 该转人工时有没有停；
- 有没有编造库存、数据、客户信息。

## 说明

所有姓名、对话、订单、价格、活动均为虚构，不对应任何真实客户。

## v1.2 角色与目录案例

- [单会话朋友圈草稿](super-agent-dispatch/input.md)：核对 [输出边界](super-agent-dispatch/expected.md)。
- [商品依赖交接](role-dependency/input.md)：核对 [输出边界](role-dependency/expected.md)。
- 安装后的首次使用直接读 [随包演练](../.agents/skills/private-domain-ops/references/examples/first-task.md)，无需克隆示例目录。

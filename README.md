# 私域 AI 运营系统技能库

本仓库是微信 AI 私域运营系统技能的版本管理入口，归属 GitHub 账号 `WeChat-AI-Skills`。

## SCRM 上岗与操作技能

覆盖首次上岗、朋友圈排期、好友消息、客户群邀请和好友关系清理。各企业的实际入口以当前界面、工作号及权限为准。

| 技能 | 适用场景 |
| --- | --- |
| [SCRM 上岗检查](.agents/skills/wechat-scrm-onboarding/SKILL.md) | 首次核对企业、账号、权限和四项入口 |
| [朋友圈图文排期](.agents/skills/wechat-scrm-moments/SKILL.md) | 准备、排期、原地修改和逐账号结果回读 |
| [好友消息](.agents/skills/wechat-scrm-friend-message/SKILL.md) | 单人或指定名单的文字、图片与小程序，核对发送结果 |
| [现有客户群邀请](.agents/skills/wechat-scrm-group-invite/SKILL.md) | 核实资格和在群状态，核对群邀请卡出站及入群 |
| [好友关系复核与清理](.agents/skills/wechat-scrm-friend-cleanup/SKILL.md) | 核实关系、准备名单、删除排期和逐人核验 |

## 配套运营技能

| 技能 | 适用场景 | 使用条件 |
| --- | --- | --- |
| [微信活动与礼赠答疑交接](.agents/skills/wechat-activity-customer-handoff/SKILL.md) | 顾客主动询问活动或礼赠时，核实依据、起草、交接并核对人工处理回执 | 合成演练可直接使用。业务任务依赖获授权的活动规则和人工服务渠道 |
| [有赞加购未购核验](.agents/skills/audit-youzan-cart-nonbuyers/SKILL.md) | 核对同一窗口的加购与已购客户，去重并排除已购 | 聚合脚本使用 Python 3.10+ 标准库，实际核验依赖已授权且可对账的两份输入 |

## 使用与维护

从仓库根目录开启 Codex，按表中技能名称调用。新技能放在 `.agents/skills/<skill-name>/SKILL.md`。目录名与 `name` 一致，`description` 告知 Agent 何时调用。随技能版本维护的脚本、模板和参考文档放进同一目录，用相对路径引用。新增或修改后更新技能清单。

仓库保存技能说明、代码、模板和合成示例。真实客户数据、聊天原文和生产凭据保存在各自获授权的业务环境中。

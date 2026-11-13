# 项目整合记录

导入源：`WeChat-AI-Skills/wechat-private-domain-skills` v0.1.0，提交 `07466b3206ad6bed1fd14e64f79512584aec5bf2`。

原项目 41 个文件均已归入下表对应位置，4 次提交通过合并历史保留。业务技能和示例经过校正，安装入口改为完整包复制安装。图片保持原字节，许可声明保留。

| 原文件 | 当前路径 | 处理 |
| --- | --- | --- |
| `.gitignore` | `.gitignore` | 整合修订 |
| `LICENSE` | `licenses/deepseek-skills-MIT.txt` | 原样保留 |
| `README.md` | `README.md` | 整合修订 |
| `assets/architecture.jpg` | `assets/architecture.jpg` | 原样保留 |
| `assets/cover-v2.jpg` | `assets/cover-v2.jpg` | 原样保留 |
| `assets/scene-campaign.jpg` | `assets/scene-campaign.jpg` | 原样保留 |
| `assets/scene-intake.jpg` | `assets/scene-intake.jpg` | 原样保留 |
| `assets/scene-moments.jpg` | `assets/scene-moments.jpg` | 原样保留 |
| `docs/boundaries.md` | `docs/boundaries.md` | 整合修订 |
| `docs/method.md` | `docs/method.md` | 整合修订 |
| `docs/tool-contract.md` | `docs/tool-contract.md` | 整合修订 |
| `examples/README.md` | `examples/README.md` | 整合修订 |
| `examples/campaign-invite/expected.md` | `examples/campaign-invite/expected.md` | 整合修订 |
| `examples/campaign-invite/input.md` | `examples/campaign-invite/input.md` | 整合修订 |
| `examples/night-inquiry/expected.md` | `examples/night-inquiry/expected.md` | 整合修订 |
| `examples/night-inquiry/input.md` | `examples/night-inquiry/input.md` | 原样保留 |
| `examples/week-of-moments/expected.md` | `examples/week-of-moments/expected.md` | 整合修订 |
| `examples/week-of-moments/input.md` | `examples/week-of-moments/input.md` | 整合修订 |
| `install.sh` | `install.sh` | 整合修订 |
| `scripts/validate_skills.py` | `scripts/validate_skills.py` | 整合修订 |
| `skills/campaign-invite/SKILL.md` | `.agents/skills/campaign-invite/SKILL.md` | 整合修订 |
| `skills/campaign-invite/references/run-of-show.md` | `.agents/skills/campaign-invite/references/run-of-show.md` | 整合修订 |
| `skills/campaign-invite/references/segmentation.md` | `.agents/skills/campaign-invite/references/segmentation.md` | 整合修订 |
| `skills/customer-intake/SKILL.md` | `.agents/skills/customer-intake/SKILL.md` | 整合修订 |
| `skills/customer-intake/references/question-bank.md` | `.agents/skills/customer-intake/references/question-bank.md` | 整合修订 |
| `skills/customer-intake/references/reply-patterns.md` | `.agents/skills/customer-intake/references/reply-patterns.md` | 整合修订 |
| `skills/customer-profile/SKILL.md` | `.agents/skills/customer-profile/SKILL.md` | 整合修订 |
| `skills/customer-profile/references/profile-schema.md` | `.agents/skills/customer-profile/references/profile-schema.md` | 整合修订 |
| `skills/customer-profile/references/tag-system.md` | `.agents/skills/customer-profile/references/tag-system.md` | 整合修订 |
| `skills/followup-plan/SKILL.md` | `.agents/skills/followup-plan/SKILL.md` | 整合修订 |
| `skills/followup-plan/references/frequency-rules.md` | `.agents/skills/followup-plan/references/frequency-rules.md` | 整合修订 |
| `skills/followup-plan/references/stage-playbook.md` | `.agents/skills/followup-plan/references/stage-playbook.md` | 整合修订 |
| `skills/moments-calendar/SKILL.md` | `.agents/skills/moments-calendar/SKILL.md` | 整合修订 |
| `skills/moments-calendar/references/content-pillars.md` | `.agents/skills/moments-calendar/references/content-pillars.md` | 整合修订 |
| `skills/moments-calendar/references/publish-checklist.md` | `.agents/skills/moments-calendar/references/publish-checklist.md` | 整合修订 |
| `skills/private-domain-ops/SKILL.md` | `.agents/skills/private-domain-ops/SKILL.md` | 整合修订 |
| `skills/private-domain-ops/references/handoff.md` | `.agents/skills/private-domain-ops/references/handoff.md` | 整合修订 |
| `skills/private-domain-ops/references/routing.md` | `.agents/skills/private-domain-ops/references/routing.md` | 整合修订 |
| `skills/sales-review/SKILL.md` | `.agents/skills/sales-review/SKILL.md` | 整合修订 |
| `skills/sales-review/references/evidence.md` | `.agents/skills/sales-review/references/evidence.md` | 整合修订 |
| `skills/sales-review/references/rule-card.md` | `.agents/skills/sales-review/references/rule-card.md` | 整合修订 |

主要修订：统一安装目录和技能间依赖；按当前/持续授权执行；将示例频控改为待确认参数；修正近似预算、商品依据、名单集合、时间和状态；保留工具设计为未实现接口参考。

原项目演示图完整保留，图中文字属于演示语境。当前执行与验收以技能和客户实际资料为准。

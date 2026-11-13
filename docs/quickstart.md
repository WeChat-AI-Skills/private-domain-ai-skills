# 安装、上岗与更新

## 1. 准备

客户需要 Python 3.10 或更新版本。使用克隆方式时还需要 Git；也可下载固定版本完整 ZIP 后解压。本仓库公开可读，下载和克隆无需 GitHub 登录。Codex 是首个核验宿主。其他 Agent 可按其技能目录配置安装目标，识别能力需在该宿主单独验证。

技能安装完成后，使用客户自己的 SCRM 会话及业务工具配置；业务凭据通过对应受控入口提供，不需要交给 GitHub。

## 2. 取得固定版本

可从 [v1.2.2 发布页](https://github.com/WeChat-AI-Skills/private-domain-ai-skills/releases/tag/v1.2.2)下载完整 ZIP 与 SHA256SUMS.txt。ZIP 解压后同样运行下列检查和安装命令；使用 Git 时，在客户选定的本地目录执行：

```bash
git clone --branch v1.2.2 https://github.com/WeChat-AI-Skills/private-domain-ai-skills.git
cd private-domain-ai-skills
python3 scripts/check_all.py
./install.sh --dry-run
./install.sh
```

默认复制全部 15 项技能到用户主目录下的 `.agents/skills`。也可指定工作区或其他宿主的技能目录；本版本验证了 Codex 对工作区安装副本的原生识别：

```bash
./install.sh --target /path/to/customer-workspace/.agents/skills
```

上面的 `/path/to/customer-workspace` 是示例路径，替换为客户选定的实际目录。安装只写指定技能目录及安装回执，不登录业务系统。复制安装不会随源仓库更新自动变化。

已有同名技能、符号链接或被客户修改过的安装副本会阻止整批覆盖。先保留客户版本并比较，不能为了安装直接删除冲突。若此前使用旧项目的链接式安装，先备份并核对链接目标，再由客户决定迁移方式。

也可从本仓库根目录打开 Codex，直接使用 `.agents/skills` 中的项目技能。选一种部署方式，避免同时加载不同版本的同名技能。

## 3. 核对宿主识别

下一轮对话或重载宿主后，要求 Agent 列出已识别技能及实际路径，检查是否与 [manifest.json](../manifest.json) 的 15 项一致。能读取文件不等于宿主已加载。

首条上岗指令：

> 使用 $wechat-scrm-onboarding，复用我已提供的企业入口与业务资料，只读核对当前企业、工作号、权限和可用功能。列出可推进任务与缺口，并生成一份客户环境卡。暂不发送、排期、邀请或修改业务数据。

## 4. 客户环境与首个任务

按[客户环境卡](../.agents/skills/wechat-scrm-onboarding/references/customer-setup.md)准备品牌与商品资料、活动与服务规则、授权范围、人工接管人。资料和回执存于仓库外的客户工作区。

先用[合成示例](../examples/README.md)检查输出。随后选一个小任务，例如一条朋友圈：确认最终图文、测试账号、时间与时区 → 明确提交授权 → 查原任务 → 到期查逐账号结果。只有排期成功时，报告“已排期”。

## 5. 后续更新与回退

阅读新版本 CHANGELOG，在另一目录检出该版本并先验证，再对同一安装目标执行：

```bash
./install.sh --dry-run --update
./install.sh --update
```

自定义目标时两条命令都加上同一个 `--target`。更新只接受有本包安装回执且未被本地修改的技能；其他同名技能不会被覆盖。旧版本检出后也可用同样方式回退，但先检查版本迁移说明。

v1.0.0 → v1.1.0 会新增 task-reconcile。反向回退时旧版清单缺少这项技能，安装器会阻止覆盖；请先在另一个目录安装并验证 v1.0.0，再切换宿主的技能目录，保留原副本供恢复，避免同时加载两个版本。

更新后重新核对宿主识别、相关合成案例与客户环境变化。客户业务配置和执行回执独立保存，升级不改动这些资料。

更新期间暂停修改目标技能。若安装进程被强制终止且留下安装锁或 staging 目录，先保留目录并检查回执及 previous 备份，完成恢复后再重试；不要直接删除锁后重复覆盖。


## 6. 安装后先完成一个无业务连接的任务

请 Agent 读取安装目录中的 `private-domain-ops/SKILL.md`，按其中链接完成 `references/examples/first-task.md`。这是合成朋友圈草稿任务，不要求真实账号，也不会发布内容。

预期得到：所用角色和技能、仅基于给定事实的草稿、素材需求、完成状态和缺口。宿主没有子 Agent 时，记录 single_agent，不把职责说明说成已启动进程。

从已安装的 `private-domain-ops` 目录可运行：

```bash
python3 scripts/catalog.py
python3 scripts/catalog.py --domain moments
python3 scripts/catalog.py --role content-agent
python3 scripts/catalog.py --workflow moments-delivery
python3 scripts/catalog.py --check-task references/examples/first-task.json --result references/examples/first-result.json
```

这些命令只读取目录或检查示例结构，不联网、不委派、不发布。角色查询中的 profile_path 指向当前安装副本的可读文件，profile_base 说明原相对路径的解析基准；没有固定开发机路径。没有本地命令工具的 Agent 可直接读取对应 JSON 和 Markdown。查询结果不是宿主识别证据，仍需按第 3 节检查宿主加载。

v1.1.1 → v1.2.0 保留 15 项名称及路径，增加总控资料。用完整安装包执行 --update，不能只复制 SKILL.md。未修改副本可回退到 v1.1.1；任务产物始终保存在安装目录之外。迁移细节见[架构说明](architecture.md)。

v1.2.0 → v1.2.1 仍是相同 15 项技能；A卷、方法许可及任务卡 1.1 随包安装。新任务采用 1.1，旧 1.0 卡片保持可读，但不代表补做了三关。执行前仍须按当前 A卷补齐必要判断；检查器不代替真实授权审核。未修改的技能副本可用旧包 --update 回退到 v1.2.0；新增任务卡留在工作区，用新检查器读取，旧检查器不支持 1.1。

## v1.2.2 升级与兼容

使用 v1.2.2 完整包，对已有目标先执行 `--dry-run --update`，再执行 `--update`。15 项技能名称和路径、安装回执版本及逐对象结果契约 1.0 保持不变。安装器检测到客户修改会整批停止，先备份并比较修改，不自动合并或覆盖。

新任务/结果卡采用 1.2；旧 1.0/1.1 卡仍按原规则读取，不能据此推断已补做新版证据检查。升级任务须显式转换并重新核对，不能只把新字段混入旧版本。首次合成草稿仍只用一张 L1 短卡；独立审查或 L3 完成声明才需要对应证据记录，见[约定](../.agents/skills/private-domain-ops/references/recovery-and-review.md)。

未修改副本可以用 v1.2.1 或 v1.1.1 的完整包对同一目标执行 `--update` 回退，再用 v1.2.2 包重新升级。任务、客户配置和运行证据应一直保存在安装目录以外；回退只换技能文件，不转换或删除工作区卡片。v1.2.1 检查器会拒绝 1.2 卡片，v1.1.1 不提供该任务卡检查器；需要读取新卡时使用 v1.2.2 检查器。

[本版本验证](verification-v1.2.2.md)分别记录新装、直升、客户修改保护、回退、再升级和宿主识别。真实工具适配与业务现场验收安排在后续 v1.3。

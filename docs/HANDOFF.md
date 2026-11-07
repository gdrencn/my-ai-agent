# Maa development handoff

交接日期：2026-11-07。面向另一台机器上的 Codex，记录已确认的产品决定、验收和后续方向。本文件只迁移项目知识，不包含个人凭据或原始会话。

## 先读与接手

先读取 [AGENTS.md](../AGENTS.md)、本文件、[REQUIREMENTS.md](../REQUIREMENTS.md)、[IMPLEMENTED.md](../IMPLEMENTED.md)、[开发与发布流程](DEVELOPMENT.md)。按需继续读 [README.md](../README.md)、[独立性约定](INDEPENDENCE.md)、[测试覆盖对照](TEST_COVERAGE.md) 和 [已解决问题](KNOWN_ISSUES.md)。当前需求优先于历史归档；本文件是有日期的快照，不能替代后续提交中的实际需求与实现。

新机器可从仓库开始：

```bash
git clone https://github.com/gdrencn/my-ai-agent.git
cd my-ai-agent
git status --short --branch
git log -5 --oneline
codex
```

已有工作区先检查未提交修改和分支差异，再同步；不要直接覆盖。给新 Codex 的接手提示可使用：

```text
请读取 AGENTS.md、docs/HANDOFF.md、REQUIREMENTS.md、IMPLEMENTED.md 和 docs/DEVELOPMENT.md，核对代码与 GitHub main。
先汇报当前版本、已完成范围、必须保留的架构与测试，以及 0.2.x Web 尚待确认的问题。
接下来先讨论 Web 方案；这条接手提示不授权新功能开发、安装服务或修改已发布资产。
```

默认中文沟通；代码、命令、标识符保留英文。用户提出想法或询问方案时先讨论，明确授权后执行。已授权的开发、验收、test 发布应持续完成；stable 发布必须取得用户验收后的明确授权。阶段结束先对照需求核验，再更新实现文档。文档用英文文件名，保存在项目内。不要修改开发机器的全局 Codex 数据、全局 AGENTS.md 或通用开发/交互规范。

## 当前交付状态

交接前 main 的基线提交：`664cc5afe121d56c35f788513b69bf09b772c0b2`。本次交接提交只更新文档和项目指引，不增加产品版本。

| 项目 | 已核实状态 |
| --- | --- |
| 正式版本 | [stable/0.1.16](https://github.com/gdrencn/my-ai-agent/releases/tag/stable/0.1.16)，GitHub latest，2026-11-03 发布 |
| 正式标签提交 | `5ce3f35b2d88016ca856d25928d080c93793e6b6` |
| 配对测试版本 | [v0.1.16](https://github.com/gdrencn/my-ai-agent/releases/tag/v0.1.16)，prerelease |
| 测试标签提交 | `c4175efd99d05bb11f7961375f6c0318deb1afd6` |
| stable/test 产品与测试包 | 两个渠道分别字节一致；渠道元数据、安装入口和清单不同 |
| 用户验收 | 0.1.16 升级、新装均通过 158 项配对测试和 42 项原生验收，用户随后授权 stable |
| 当前实现范围 | 本地模型底座、Codex CLI、配置和菜单；没有 Web 或 IM 功能 |
| 旧版本 | stable/0.1.9、既有 test、标签及资产保留，不替换 |
| 工作尾项 | stable 已完成，不存在需要接手继续执行的发布步骤；后续新功能先讨论 |

已验收且冻结的归档 SHA-256：

```text
f83044d8bad999dd7b077b3eb21a38f0f6e267c13753d2e32483c4bd9f1347f1  maa.pyz
fe7fcba85e4d6bf4ed9c994105f71835f72676294b56dceaced66d450e31811e  maa-test.pyz
```

**历史实验版本 v0.2.1、v0.2.2 已经存在。** 它们来自曾经进行的 IM 试验；后来按用户决定回到 0.1.9 基础完成独立性重构与修复，形成当前 0.1.16。不要把旧 IM 实验分支当成当前开发基线，不要按数字大小自动选择它们。未来 Web 的具体版本号待确认，不能覆盖这些已交付版本。

正式安装：

```bash
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/install.sh | bash
```

正式版安装后完整验收：

```bash
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/install.sh | bash -s -- --test
```

当前测试版完整验收：

```bash
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/test/test.sh | bash
```

正常正式安装不下载验收小模型；完整配对验收会下载并保留模型。test 入口固定 v0.1.16，避免选中历史 0.2.x 实验版。`test/install.sh` 安装 test 但不自动跑测试。`--components none` 仅跳过官方组件安装，不减少 `--test` 验收。支持显式 `--version 0.1.16` 和 `--language zh_cn` / `en_us`。旧 stable 可以显式选择 `--version 0.1.9`，但旧产品仍适用自身历史环境要求。

## 产品边界：不能再次改变的原则

1. Maa 是独立 Linux 产品，不依赖 mas，也不应识别 mas 是否存在。mas 是另一个负责创建和管理 Linux 容器的产品，与 Maa 业务无关。不得检测容器来源、假定在或不在容器内、依赖预装镜像，或调用外层管理接口。
2. Maa 只操作自己所在 Linux 环境。没有穿透到宿主机或扩大容器权限的需求，不得增加访问外层命名空间、外层容器管理或宿主控制的功能。测试同样不假设环境来源。
3. systemd 是 Maa 对所有安装环境一致的实际运行要求。检查 Linux、Python 3.11+、可访问的 systemd 系统管理器和所需依赖；通过共享包管理表准备缺少的工具。不安装 init、不增加软件源、不整机升级、不修改外层环境。
4. Maa 管理命令执行后退出。当前没有 Maa 常驻守护进程、Responses 代理或对话桥接。已生成的原生服务和 Codex 配置在 Maa 不运行、甚至其归档被移走后仍能使用。
5. Codex 直接连接原生底座接口，上下文和会话历史由 Codex 保存。Maa 不处理对话内容，不伪造请求统计。
6. CLI、菜单及未来界面复用共享业务模块；配置、输出、依赖与服务生命周期不能各写一套。
7. 不替用户限制原生 HOST 配置。YOLO 开关只按已确认规则配置与恢复权限，用户如何使用该权限不属于 Maa 的控制范围。
8. 对既有归属不明的命令、服务、配置和文件先拒绝或明确报告，不能为了安装成功覆盖它们。失败回滚与 Ctrl+C 退出码 130 必须保留。

`codex-local` 的核心内容是独立 shell 入口：

```sh
export PATH="$HOME/.local/bin:$PATH"
exec codex --no-daemon --profile maa-local "$@"
```

入口不调用 Maa/Python，不加载管理状态，不暗中启动已暂停的底座。`"$@"` 原样传递其他参数，参数冲突由官方 Codex 判断。两个固定参数不需要重复指定。PATH 补充只影响入口自身，确保官方用户安装后不必重启父 shell。

## 已实现行为与容易退化的地方

- Ollama 使用原生模型/tag、原生 pull 和 GGUF 导入；llama.cpp 支持 HF 精确 GGUF 与本地 GGUF 登记。HF 仍是“仓库标识＋精确文件名”两个输入，不改成曾讨论后取消的单字段 shorthand。
- 模型身份包括底座、原生 digest，或 HF 提交/文件，或本地路径/SHA-256。分片必须完整验证；文件变化或缺失在停止现有服务前拒绝。
- 每个准确模型独立保存上下文、主 KV、Flash Attention、fit、显存预留、keep-alive、MTP 和 MTP KV。默认值与完整枚举以 README/settings.py 为准。MTP 能力根据真实权重与运行器判断。
- 配置切换使用候选事务，成功后才提交与启用自启动；失败、中断恢复已接受目标。暂停释放模型资源但保留选择及启动目标；启动复用有效原生配置，空闲模型复用底座唤醒。
- 底座参数变化需要加载；Codex 推理强度、全局 YOLO、语言、只读查询、未变化配置不重载底座。更新当前底座与更新 Codex 的影响不同。
- 已核验的原生地址需持久保留。启动、唤醒、状态、readiness、运行中 Ollama 清单与下载/导入使用同一已接受地址；新候选与回滚不能误用其他监听实例。
- 菜单只读项按 Enter/右键保持原页面。选项包含语言与关于；首次安装选择语言，升级沿用保存值。NO_COLOR 不丢失配置含义。
- 资源数据来自实际驱动/API/当前启动日志。未知保持未知，不填 0；GPU 可用量不靠减法替代驱动值。GPU、系统内存、RS、MTP 分项区分；暂停后不展示旧分配。小模型无 MTP，不宣称真实 MTP 性能已验收。
- profile/catalog 保留原生模型身份与实际上下文，压缩阈值为有效上下文的 90%；不覆盖普通 Codex 模型配置，不给 profile 强加全局权限或 web search。
- 首次安装仅一次默认开启全局 YOLO；升级、重装和更新 Codex 保留选择。只备份/恢复 `approval_policy`、`sandbox_mode` 的原值与存在状态，保留其他 TOML。
- 特权命令共用原生 sudo 通道。密码只由 sudo 从控制终端读取，Maa 不收集密码；提示立即可见，认证时暂停计时刷新。非交互使用 sudo -n，避免隐藏等待。
- 进程清理只针对自身拥有并核验身份的进程。Codex 客户端使用独立 session；需要 sudo 的原生管理调用在现有 session 内拥有新进程组并交还前台终端。不能混用两者或按程序名杀进程。

## 源码定位

| 文件或目录 | 职责 |
| --- | --- |
| [maa/cli.py](../maa/cli.py)、[maa/ui.py](../maa/ui.py)、[maa/menu.py](../maa/menu.py) | CLI、菜单入口和呈现 |
| [maa/manager.py](../maa/manager.py) | 模型选择、配置和管理事务 |
| [maa/service.py](../maa/service.py) | 原生 unit、归属、已保存地址、启动/暂停/回滚、特权调用 |
| [maa/models.py](../maa/models.py)、[maa/gguf.py](../maa/gguf.py)、[maa/backends.py](../maa/backends.py) | 模型清单、下载/登记、GGUF 与底座原生参数 |
| [maa/telemetry.py](../maa/telemetry.py) | 实际状态、当前日志和资源观测 |
| [maa/codex.py](../maa/codex.py)、[maa/agent_status.py](../maa/agent_status.py) | profile/catalog、独立入口、YOLO、原生配置读取 |
| [maa/store.py](../maa/store.py)、[maa/settings.py](../maa/settings.py) | 原子状态、锁、设置与约束 |
| [maa/environment.py](../maa/environment.py)、[maa/http.py](../maa/http.py) | 依赖/包管理表、实际运行条件、共享原生请求/IPv6 |
| [maa/output.py](../maa/output.py)、[maa/processes.py](../maa/processes.py) | 输出、进度、捕获与实时诊断、拥有进程清理、终端恢复 |
| [maa/install.py](../maa/install.py)、[bootstrap.py](../bootstrap.py) | 安装事务、官方安装器、归档配对验证 |
| [maa/preferences.py](../maa/preferences.py)、[maa/i18n.py](../maa/i18n.py)、[maa/locales](../maa/locales)、[maa/text.py](../maa/text.py) | 偏好、双语目录、呈现文字 |
| [scripts/build.py](../scripts/build.py)、[scripts/entry.template.sh](../scripts/entry.template.sh) | 确定性打包与三个生成式安装入口 |
| [tests](../tests)、[scripts/test_bootstrap.py](../scripts/test_bootstrap.py) | 隔离便携/PTY 测试、交付测试 |
| [test/native.py](../test/native.py)、[test/installed.py](../test/installed.py)、[test/codex_ui.py](../test/codex_ui.py)、[test/codex_tool.py](../test/codex_tool.py) | 实际安装观察、完整原生验收、实际 Codex 客户端与工具协议 |
| [test/coverage.py](../test/coverage.py)、[scripts/check_coverage.py](../scripts/check_coverage.py) | 不可缩减的覆盖清单与机器可读对照 |
| [docs/VENDOR.json](VENDOR.json) | 固定 vendored tomlkit 及许可证来源 |
| [validation](../validation)、[.github/workflows/check.yml](../.github/workflows/check.yml) | 历史实际证据与 CI 流程 |

## 测试：只能增加覆盖，不能借解耦减少

| 套件 | 0.1.9 | 0.1.16 | 丢失 |
| --- | ---: | ---: | ---: |
| 便携 / 实际 PTY | 90 | 158 | 0 |
| 交付测试 | 10 | 13 | 0 |
| 完整原生验收 | 35 | 42 | 0 |

0.1.10 新增检查也保留。清单存在不代表实测通过；每项原生检查必须实际执行并记录。完整项目与逐项对应见 [TEST_COVERAGE.md](TEST_COVERAGE.md)。

**YOLO 是改断言方式，不是删测试。** 开启、关闭、恢复、重装保留都要测；使用私有 CODEX_HOME，通过原生 Agent `config/read` 返回判断权限状态，不执行某个必然触发确认的操作来推断。用户真实权限及恢复文件内容/权限位应保持不变。

真实 Codex 对话、函数声明与调用、固定 shell 结果回放、stream/nonstream Responses、模型 picker、实际 profile/catalog、暂停/唤醒/复用、中断恢复、加载失败回滚、重装都继续验收。不要把真实工具协议测试混同 YOLO 状态测试后删除。私有客户端必须使用 Maa 真正写出的 profile/catalog，不能重新生成一份绕过被测配置。

便携检查在隔离目录及假依赖中执行，不安装真实包，不操作开发主机服务：

```bash
python3 scripts/test_bootstrap.py
python3 -m unittest discover -v -b
python3 scripts/check_coverage.py --output /tmp/maa-coverage.json
```

有业务改动时按 [DEVELOPMENT.md](DEVELOPMENT.md) 确定性构建两次、比较归档，并从仓库外执行配对便携测试：

```bash
python3 scripts/build.py --channel test
# 将下面绝对路径改为实际仓库位置；从 /tmp 执行，避免借用源码导入。
cd /tmp
python3 -I /absolute/project/dist/maa-test.pyz --unit --product /absolute/project/dist/maa.pyz
```

构建会重新生成根目录与 test 安装入口；检查 diff，不要提前发布新的公共版本指针。原生安装/验收会安装官方软件、下载模型、切换原生服务，不能作为无副作用的源码检查直接在开发主机运行。应在为验收准备、明确授权的 Linux 身份和资源上执行，不假设某个容器产品或预装软件。

普通用户与 root 都需要覆盖；GPU 存在时保留实际 GPU 断言，CPU 环境明确记录不可用并执行真实主机内存断言。成功验收保留下载模型，最终暂停测试目标；失败/中断清理坏夹具、私有客户端/权限目录和自有临时进程，不误杀无关进程或系统服务。实际密码、Token、真实会话不写入报告。

## 已完成验收的证据

这些是既往实测，不能冒充新机器或新依赖版本的实测。0.1.16 测试时包含 Codex 0.166.0、用户日志中的 llama.cpp b12019；它们不是未来安装器应硬编码的“最新版本”。

- [V0_1_16_LOCAL.json](../validation/V0_1_16_LOCAL.json)：便携、打包、交付与隔离复现。
- [V0_1_16_NATIVE.json](../validation/V0_1_16_NATIVE.json)、[V0_1_16_ROOT_NATIVE.json](../validation/V0_1_16_ROOT_NATIVE.json)：普通用户/root 各 42 项完整原生验收。
- [V0_1_16_ENDPOINTS.json](../validation/V0_1_16_ENDPOINTS.json)：0.1.15 原生配置升级、自定义地址、环境变量消失后的实际连接与唤醒。
- [V0_1_16_TIMEOUT.json](../validation/V0_1_16_TIMEOUT.json)、[V0_1_16_AUTHENTICATION.json](../validation/V0_1_16_AUTHENTICATION.json)：临时 Ollama 超时清理、classic sudo / sudo-rs 认证、取消、超时、终端恢复。
- [V0_1_16_COVERAGE.json](../validation/V0_1_16_COVERAGE.json)：覆盖对应；[V0_1_16_PUBLIC.json](../validation/V0_1_16_PUBLIC.json)、[V0_1_16_PUBLIC_NATIVE.json](../validation/V0_1_16_PUBLIC_NATIVE.json)：test 公共入口实际验收。
- [STABLE_0_1_16_REVIEW.json](../validation/STABLE_0_1_16_REVIEW.json)、[STABLE_0_1_16_PUBLIC.json](../validation/STABLE_0_1_16_PUBLIC.json)、[STABLE_0_1_16_NATIVE.json](../validation/STABLE_0_1_16_NATIVE.json)：用户授权 stable、相同归档、公开安装、158＋42、四种渠道/显式版本重装与旧版解析。
- [VALIDATION_SHA256SUMS](../validation/VALIDATION_SHA256SUMS)、[stable 公共证据清单](../validation/STABLE_0_1_16_PUBLIC_SHA256SUMS)：证据文件校验。

正式安装默认不下载测试模型已单独验证；完整验收使用小模型。Maa 归档移走后真实 Codex 仍能对话、原生服务独立工作也在验收内。发布时创建的临时验收环境已经清理；不要假设原机器的 /tmp 脚本、远程身份、GPU、登录态或测试资源仍可使用。

## 历史问题：避免重蹈覆辙

| 问题 | 已确认的处理与边界 |
| --- | --- |
| 实时显示重复回复前缀 | 旧时期出现过实时回复重复而历史回放正常。保留的产品决定是移除 Maa 对话代理，让 Codex 直连原生接口。具体模型/SSE 内部机制没有完整实验证明，不把推测写成确定根因，不重新引入相同桥接架构。 |
| 解耦时测试缩水 | 0.1.10 曾误将普通环境可测试扩大成削减功能验收；后续恢复完整覆盖。独立性只改变环境假设及 YOLO 判断方式，不能降低模型、对话和生命周期测试。 |
| 临时 Codex 目录 ENOTEMPTY | 插件 clone 的子进程在父进程退出后继续写目录；先停止并等待自有 session 内子进程，再清理临时目录。正常/失败/超时/中断与独立进程组均覆盖，不关闭插件规避。 |
| sudo 提示不可见、等待超时 | 通用捕获隐藏了认证诊断。修复共享实时 stderr、控制终端与前台交还；保留 JSON stdout。不能把交互 sudo 放进脱离控制终端的 session。 |
| CA 目录被误判缺失 | OpenSSL 的 hashed CA 目录可能延迟加载，不能凭 get_ca_certs() 为空就安装证书包。离线核验有效目录，继续严格 TLS 校验。 |
| IPv6 与通配监听 | 正确保留方括号与端口；客户端可选对应 loopback，原生 bind 不改。 |
| 原生地址随 shell 环境丢失 | 0.1.16 复用已核验持久地址；候选/已接受目标/回滚语义分开。 |
| 原生验收超时残留临时 Ollama | 0.1.16 共享拥有进程组清理，同时保留 sudo 终端，不影响无关组和原生 systemd 服务。 |
| 清理异常覆盖安装原错 | 记录二次错误，保留原始失败及中断 130；单独清理失败仍应失败。 |

用户曾遇到官方 Codex 安装器跳过旧版本清理的 warning；后续安装与验收通过。没有确定该官方清理警告的具体根因，不因此自行修改官方安装器。

## 发布规则

以 [DEVELOPMENT.md](DEVELOPMENT.md) 为准：代码、文档及配对版本一致；自检、完整适用验收和 CI 通过后发布已核实资产，再移动 main 公共入口，最后验证真实公开命令。用户收到某个 test 后的新修复使用新版本，不替换其资产。纯交接文档不增加产品版本。

发布资产至少包含配对的 `maa.pyz`、`maa-test.pyz`、`VERSION.json`、`bootstrap.py`、渠道适配的 `install.sh`、`SHA256SUMS`，以及相应验收证据与校验清单。匿名重新下载，对比本地字节、GitHub digest、清单；验证新装/更新和前版资产不变。不要把 draft 或仅上传部分资产的 release 当作可交付版本。

stable 只能由用户明确验收后发布，产品与配对测试包原样采用已验收 test 字节；渠道元数据、入口、清单和证据可以不同。不要为了 stable 重新修改业务代码。旧 stable 保留，明确版本可选择；旧版不承诺未来环境兼容。

## 已讨论的下一阶段：0.2.x Web，0.3.x IM

以下是用户确认的产品方向，**具体实施方案、范围和新版本号尚待讨论授权**。

### 0.2.x Web

- Web 是 Maa 新增的一项功能，不另造一个名为“maa web”的独立产品。
- 外部浏览器能够访问当前 Linux 环境中的界面，测试场景包括 Windows localhost。
- 提供 Web shell 操作 Maa 所在 Linux 环境，提供与 Agent 对话的界面。
- 不要求 mas，不识别安装来源，不通过外层管理接口或宿主权限突破当前边界。监听、映射和外部访问的具体部署条件仍要确认，不能假定各环境 localhost 转发完全相同。
- 先讨论：首个里程碑页面/操作范围；认证与会话；监听地址/端口；浏览器通信与终端；Codex 原生协议；断线/取消/多会话；安装依赖；组件启停/卸载；现有菜单/CLI 的共享调用；验收环境与覆盖。
- 需要显式说明 Web 运行组件如何被管理，以及其与一次性 Maa 管理工具的关系。不能默默恢复 Maa 对话代理或扩大原有核心进程职责。

当前没有已批准的 Web 框架、协议、端口、服务单元或界面设计；不要从历史聊天中的研究想法推断它们已经定稿。

### 0.3.x IM

- 当前 0.1.x 不含 IM。将来接入 Telegram / WhatsApp / WeChat。
- Maa 可安装、配置和管理小组件；IM 与 Codex 的连接器属于为 Maa 功能开发的独立组件，不让 Maa 本体常驻转发对话。
- 分为各平台官方规范适配层与共享内容处理层；Codex 连接另行设计，上下文由 Codex 管理。
- Telegram 支持多个 bot；WhatsApp 和 WeChat 当前方向各支持一个。
- 先完成平台基础认证与固定文本收发，再接 Codex；需要本地干净关闭、导入/导出、删除和恢复，不要求远端解绑。
- WeChat 不要求安装 OpenClaw。自研连接器不能被称作官方提供的独立连接器包。实施时重新核对三家实际开放的官方 API、账号条件与标准接入流程；旧实验代码和当时 API 研究不能直接作为现行保证。

## Codex 跨机器继续工作的选择

2026-11-07 已查阅 [OpenAI 官方 Remote connections](https://learn.chatgpt.com/docs/remote-connections#hand-off-a-chat-between-hosts) 和 [Projects and chats](https://learn.chatgpt.com/docs/projects)。功能可用性以实际客户端、账户和工作区为准。

桌面端提供 **Hand off**：目标主机先连接并保存同一 Git 仓库项目，再从聊天底部运行位置选择目标并交接，转移聊天与 Git 状态，在目标工作树继续。它不是只登录同一账户就自动发生，也不保证所有依赖或运行进程迁移。

另一种方式是通过支持的远程连接继续控制原主机上的同一聊天，运算与文件仍在原主机。CLI 的 `codex resume` 用于继续可访问的已保存聊天，不能据此承诺新机器登录后自动拥有旧机器全部会话。

对这个项目，采用“Git 中的需求/实现/交接＋AGENTS.md 自动入口”作为长期依据；需要原聊天连续性时再使用官方交接或远程方式。不要把整个个人 CODEX_HOME、凭据或真实会话上传到公开仓库。本次任务只建立可移植文档，没有启用远程服务或迁移账户数据。

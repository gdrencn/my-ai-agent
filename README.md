# my-ai-agent

在 **my-ai-sandbox（mas）容器内**安装并管理 Ollama、llama.cpp 和 Codex CLI。

当前稳定版本：**0.1.9 stable**。两种底座可共存，通过 `maa` 选择一个当前底座和模型，并同步 `codex-local`。stable 的产品与配对测试包和已验收的 `v0.1.9` test 逐字节相同。

安装、模型切换和暂停/启动共用进度反馈：静默阶段原地刷新等待时长，原生下载保留实时进度，实际诊断单独保留；不因无输出的命令增加重复提示或空行。

## Install

先进入 mas 容器，在容器终端执行：

```bash
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/install.sh | bash
```

默认安装 maa，并依次运行 Ollama、llama.cpp、Codex 的官方安装程序。需要容器内 sudo 权限、网络、Python 3.11+、curl 和 systemd。mas 默认 Ubuntu 24.04 环境符合 Python 要求。官方程序安装完成后，maa 写入两种底座各自的原生 systemd 配置，只启用当前底座。maa 本身没有常驻服务。

只安装管理程序，之后在菜单选择软件：

```bash
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/install.sh | bash -s -- --components none
```

已有底座和模型时，也可用上述 `--components none` 命令升级 maa，保留已下载模型和配置。

根 `install.sh` 默认选择 GitHub latest 正式 stable release；`test/install.sh` 安装最新数字 test prerelease，`test/test.sh` 安装并运行该 test 版本的配对测试。指定版本可在上述命令的 `bash -s --` 后增加 `--version 0.1.9`，只在对应通道查找；stable tag 为 `stable/0.1.9`，test tag 为 `v0.1.9`。安装器核对版本、通道和 SHA-256，不把两个通道混用。

从旧版本升级时，会核验并移除项目自己的 `maa.service`，保留模型、每模型配置和 YOLO 恢复记录，然后生成原生配置并核验保存目标。原来运行的目标恢复运行，原来暂停的目标核验后恢复暂停。修改过或属于其他用户的服务会被拒绝处理；尚未选择模型时，在菜单选择模型。

安装完成后运行：

```bash
maa
codex-local
```

当前终端找不到命令时，打开新终端，或使用 `~/.local/bin/maa`、`~/.local/bin/codex-local`。maa 首次安装时默认开启当前容器用户的 Codex 全局 YOLO；菜单可关闭并恢复原来的两项设置，后续更新保留用户选择。

## Models

菜单“本地模型管理 → 安装 / 登记新模型”支持：

- Ollama 官方模型：输入名称/tag，使用原生 `pull`。
- Ollama 本地 GGUF：输入模型名称与已有 GGUF 路径，原生导入。
- llama.cpp HF GGUF：输入仓库标识和**精确文件名**，缺一不可。
- llama.cpp 本地 GGUF：登记已有文件。

例如：

```text
HF repository: unsloth/Qwen3-0.6B-GGUF
GGUF filename: Qwen3-0.6B-Q4_K_M.gguf
```

HF 页面网址不是仓库标识。子目录必须包含在文件名里；分片 GGUF 填第一片，自动下载同一提交的完整分片集合。缓存校验官方文件大小和可用的 LFS SHA-256，损坏分片单独重下。登记记录包含全部分片，缺失或变化会在停止当前模型之前拒绝；旧版本不完整的分片记录需要重新登记第一片。不搜索在线模型、不转换 Safetensors、不替换用户指定的量化版本。需要 HF 认证时可在运行安装命令的终端设置 `HF_TOKEN`；maa 不把令牌写入模型配置或服务文件。

下载完成不自动切换。进入“本地模型管理 → 设置本地模型”，默认定位当前底座和模型，当前模型有文字标记，焦点详情显示文件名与来源。正在运行的托管 Ollama 清单直接读取原生 API，不暂停模型；需要临时 Ollama 服务时才协调暂停和恢复。llama.cpp 清单显示 maa 已下载或登记的 GGUF。

HF 下载和本地文件扫描不占用全局管理锁，可在另一个终端暂停或切换模型。运行中的托管 Ollama 下载也释放该锁；暂停或切换会停止它所依赖的原生服务，可能中断下载，重新运行原生命令可以重试。需要临时 Ollama 服务的操作仍保持独占生命周期。重新下载当前 Ollama tag 会使其参数需要重新核验，下次显式启动或选择时重新应用保存配置。

## Menu and model status

主菜单顶部显示当前模型和实际运行状态。菜单按任务组织：

| Main entry | Contents |
| --- | --- |
| 本地模型管理 | 设置本地模型、安装 / 登记新模型、模型配置、当前模型状态、暂停、启动、返回 |
| Codex 配置 | YOLO 模式及当前状态、返回；进入 YOLO 后选择开启或关闭（恢复原设置） |
| codex-local 配置 | 推理强度、跟随模型的只读上下文大小、固定 90% 的只读压缩阈值、应用修改、返回 |
| 安装底座 / Codex CLI | 全部安装或单独安装 Ollama、llama.cpp、Codex CLI |
| 关于 my-ai-agent | 当前 maa 版本 |
| 退出 | 结束菜单 |

配置项直接显示当前值；选中后进入修改页面。标题使用正常文字颜色，数值与枚举为青色，开启与运行中为绿色，关闭、暂停与不可用为灰色。编辑后会提示存在未应用修改；返回取消，选择应用才生效。只读上下文与压缩阈值按 Enter/右键没有激活行为，保留当前菜单；暂停或空闲时可显示明确标注的已保存核验值。`NO_COLOR` 或 `TERM=dumb` 保留文字含义。

“当前模型状态”依次显示底座、模型、运行状态、模型层 GPU 装载、权重、主 KV、循环状态 RS、计算和输出缓冲区、MTP 额外 KV 与计算、已识别显存分配合计、整卡显存、有效上下文和请求统计不可用的说明，并提供刷新和返回。主菜单顶部使用轻量查询，不读取分配日志或查询整卡显存。

Ollama 查询自己的 `/api/ps`，llama.cpp 查询自己的 `/props`；状态查询不推理、不唤醒模型、不启停服务。分项来自当前实际加载的原生初始化分配记录，GPU 与系统内存分别标注；`CPU_Mapped` 是映射量，不是实际 RSS，`CUDA_Host` 不算显存。整卡总量、已用、可用和驱动预留通过 NVIDIA 驱动读取，包含其他程序占用，不能当成当前模型完整占用。暂停或卸载后不展示旧分项；接口或当前日志不可用时显示“未取得”及原因。

直连模式下 maa 不读取或记录对话，底座没有提供可靠的最近请求 token 状态接口，因此菜单将不可用统计合并为一条说明；CLI 仍保留 null 字段。旧版本的请求统计不再使用。有效上下文仍由原生 API 读取；模型已暂停时，已保存的上下文单独标注为上次核验值。独立 MTP 权重和实时 KV token 占用不提供。MTP 共享 KV 不重复计入合计；原生验收使用无 MTP 权重的小模型，MTP 分项只有源码及日志夹具验证。

完整结构化状态和配置仍通过 `maa status` 返回，原生日志通过 `maa logs` 查看。

## Configuration and lifecycle

每个“底座＋准确模型身份”独立保存配置。Ollama 包括原生 digest；HF 包括仓库/提交/文件；本地 GGUF 包括路径和 SHA-256。

| Setting | Default | Choices |
| --- | --- | --- |
| context | 262144 | positive integer |
| main KV | q8_0 | f16 / q8_0 / q4_0 |
| Flash Attention | on | on / off |
| fit | on | on / off |
| VRAM reserve | 0 MiB | nonnegative integer |
| idle keep-alive | 5m | 5m / 10m / 30m / -1 |
| MTP | on if supported | on / off |
| MTP KV | follow main | follow / f16 / q8_0 / q4_0 |
| Codex reasoning | inherited/default | none / minimal / low / medium / high / xhigh / max / ultra |

量化 KV 需要 Flash Attention。MTP 根据真实权重元数据及运行器能力判断，不按文件名猜测；没有 MTP 权重时不可开启。MTP 候选长度没有修改入口。主 KV 变化时，跟随模式自动更新 draft KV；单独覆盖后保持覆盖值。

GPU 层数、采样、对话模板、服务地址没有修改入口，保留模型/底座预设。llama.cpp 内部使用一个推理槽，防止上下文被默认多槽平分。GPU 全量加载是优先目标，状态显示实际资源观测；底座/模型不支持的设置保留原生错误。官方安装器可能选择 CPU 构建，实际硬件支持以它的安装输出及原生运行信息为准。

首次选择模型会打开默认配置，允许在加载前修改上下文和 KV；已有配置的模型直接恢复其配置。更换底座/模型、改变底座参数会立即重新加载，并保存下次容器启动的目标。Codex 全局 YOLO、codex-local 推理强度和未变化的配置不会启停、重载或唤醒底座。推理强度使用已核验上下文保存到本地 profile，下次启动 Codex 时使用。

“启动当前模型”复用已运行实例，空闲卸载时仅唤醒模型，暂停时启动已核验的原生配置；配置缺失、变化或旧版本没有完整核验记录时重新配置和加载。更新当前底座程序需要暂停和恢复，更新 Codex CLI 不影响模型。完整触发清单见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。失败时恢复之前的选择并尝试恢复服务，报告恢复结果；Ctrl+C 完成恢复后保留中断退出码 130。检查通过之后才启用新目标的自启动。若管理进程被强制终止或容器在配置阶段掉电，自启动可能保持关闭；重新执行 `maa start` 核验保存目标。未验证的候选目标不会自启动。

“暂停”释放资源，但保留选择和自启动目标；“启动”恢复。空闲卸载保留底座服务，下一次请求由底座重新加载。`codex-local` 不在暂停状态下暗中启动模型。

管理操作立即显示阶段和累计耗时，终端内每秒刷新同一行，结束显示成功、失败或中断。原生安装器和模型下载保留自己的进度输出；期间 maa 让出显示，完成后继续累计计时。非终端仅输出开始和结束提示到 stderr，CLI 的 stdout JSON 保持可解析。

## Codex

YOLO 只管理全局 `approval_policy = "never"` 和 `sandbox_mode = "danger-full-access"`。首次开启保存原值及存在状态，重复开启不覆盖备份；关闭恢复原值，原来没有的键删除。其他 TOML 配置保留。尊重 `CODEX_HOME`。

YOLO 默认开启只发生在首次安装 maa。后续更新、重装 maa 或更新 Codex CLI 保留当前开关和原设置备份，不自动重新开启。安装前先检查已有命令归属与 Codex 配置格式，拒绝时保留原程序；入口写入失败恢复原有文件，官方依赖安装失败保留准确诊断。

`codex-local` 使用专用 `maa-local.config.toml` profile，不覆盖普通 Codex 的模型设置，也不强制 YOLO 启动参数。模型与有效上下文同步，自动压缩阈值固定为有效上下文的 90%（262144 对应 235929）。推理档位按选定字符串传递，支持情况由客户端、底座和模型决定。

`codex-local` 是独立的 shell 脚本，内容为：

```sh
export PATH="$HOME/.local/bin:$PATH"
exec codex --no-daemon --profile maa-local "$@"
```

它在自身进程中补上官方用户安装目录，因此通过绝对路径运行时不要求先重开终端，也不修改父 shell 的 PATH。随后直接启动官方 Codex，不调用 maa、不检查管理状态、不改写配置、不自动启动暂停的底座。空闲模型由底座根据正常推理请求自行唤醒。删除 maa 程序后，已生成的 profile、模型目录和原生底座配置仍能使用。

`--no-daemon` 让本次 Codex 不使用共享后台服务，直接运行会话并加载 `maa-local` profile；不停止已存在的共享服务，也不改变底座服务。用户参数通过 `"$@"` 原样传给官方 Codex，例如 `codex-local resume --last`、`codex-local -C /path/to/project`。不需要重复提供这两个已有选项；参数有效性和冲突仍由 Codex 处理，`--model` 或 `-c` 可以覆盖 profile 的对应设置。

profile 默认在 `~/.codex/maa-local.config.toml`；设置 `CODEX_HOME` 时使用对应目录。以下为 Ollama、`qwen3.8:latest`、有效上下文 262144 的示例，目录中的 `<hash>` 为实际模型元数据的内容哈希，不是字面文件名：

```toml
# Managed by my-ai-agent. Global permissions and web_search are inherited.
model = "qwen3.8:latest"
model_provider = "maa_local"
model_context_window = 262144
model_auto_compact_token_limit = 235929
model_catalog_json = "/home/sandbox/.codex/maa-model-catalogs/<hash>.json"

[model_providers.maa_local]
name = "my-ai-agent local"
base_url = "http://127.0.0.1:11434/v1"
wire_api = "responses"
requires_openai_auth = false
```

模型名、有效上下文、压缩阈值、模型目录路径和原生地址随选择同步。llama.cpp 默认地址为 `http://127.0.0.1:8080/v1`；地址使用实际底座环境配置。推理强度为默认时不写 `model_reasoning_effort`，选择具体档位时在顶层写入对应字符串。模型目录只登记当前模型，保存 `/model` 所需元数据、支持档位及项目生成的基础提示词；它不是 Maa 服务。

Ollama profile 直连其 `/v1/responses`；llama.cpp profile 直连自己的 `/v1/responses`。切换时 maa 写入对应底座的配置，随后退出。`/model`、profile 和模型目录使用原模型名称。Ollama 在原名称上应用上下文参数，并用只占清单、不复制权重的私有备份保留原模型预设；不再用不透明的运行别名。

两条路径使用原生 Responses 普通函数调用及结果回放。当前官方接口不能完整支持 Codex 的 custom/freeform 工具，因此专用模型目录不声明 freeform `apply_patch`，文件编辑使用普通 shell 工具。模型对工具调用的能力由实际模型决定，小模型可能返回错误参数或没有选择工具。maa 不转换、过滤或修补请求。模型目录不包含本机全局工作规范或云模型提示词。

maa **不写入或覆盖 `web_search` 配置**，不安装搜索 MCP。原生底座对托管搜索、命名空间工具、推理强度的支持以其官方接口为准；配置档位不保证模型支持这些能力。普通 Codex 和本地 profile 都保留正常的用户启动参数。

## CLI

```bash
maa --version
maa install ollama
maa install llamacpp
maa install codex
maa add ollama --name qwen3:0.6b
maa add llamacpp --repo unsloth/Qwen3-0.6B-GGUF --file Qwen3-0.6B-Q4_K_M.gguf
maa add llamacpp --path /absolute/path/model.gguf
maa models ollama
maa models llamacpp
maa select MODEL_KEY
maa select MODEL_KEY --set context=32768 --set kv=q4_0
maa config context=65536 mtp_kv=follow
maa status
maa pause
maa start
maa yolo off
maa yolo on
maa logs
codex-local exec --skip-git-repo-check 'Explain this directory.'
```

模型命令返回 JSON 中的 `key` 用于选择。非交互成功退出 0，失败 1，参数错误 2，中断 130；菜单取消返回上级，主菜单退出为成功。

数据默认在 `~/.local/state/my-ai-agent`（支持 `MAA_HOME` / `XDG_STATE_HOME`），程序在 `~/.local/share/my-ai-agent`。原生模型存储仍分别属于各底座。日志通过 `maa logs` 查看。

## Test

完整安装及小模型验证会修改当前选择，并显式开关 YOLO 验证工具执行与恢复；测试结束保持 YOLO 开启。请在**新建的专用临时 mas 容器**运行：

```bash
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/test/test.sh | bash
```

入口下载同版本测试包，运行 portable/PTY 检查与Qwen3-0.6B GGUF 和 Ollama qwen2.5:3b 的原生接口、真实 Codex `/model`、驻留复用、空闲唤醒、暂停恢复及失败回滚检查，保存 JSON 报告，最后暂停模型。Codex 启动检查使用不含用户安装目录的 PATH，覆盖刚安装后尚未重开终端的情况。测试产生的坏 GGUF 与登记记录在失败时也会清理；旧测试遗留文件只在路径、内容、登记身份均符合旧测试签名且未被选中时清理，保留用户的同名真实模型。大模型、MTP 实际速度和全 GPU 装载仍需使用自己的模型验收。已核验范围见 [IMPLEMENTED.md](IMPLEMENTED.md)，开发说明见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

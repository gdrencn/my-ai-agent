# my-ai-agent

在 **my-ai-sandbox（mas）容器内**安装并管理 Ollama、llama.cpp 和 Codex CLI。

当前发布目标：**0.1.1 test**。两种底座可共存，通过 `maa` 选择一个当前底座和模型，并同步 `codex-local`。

## Install

先进入 mas 容器，在容器终端执行：

```bash
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/test/install.sh | bash
```

默认安装 maa，并依次运行 Ollama、llama.cpp、Codex 的官方安装程序。需要容器内 sudo 权限、网络、Python 3.11+、curl 和 systemd。mas 默认 Ubuntu 24.04 环境符合 Python 要求。官方程序安装完成后，maa 接管底座的自动启动，避免 Ollama 官方服务与当前选定底座同时运行。

只安装管理程序，之后在菜单选择软件：

```bash
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/test/install.sh | bash -s -- --components none
```

安装完成后运行：

```bash
maa
codex-local
```

当前终端找不到命令时，打开新终端，或使用 `~/.local/bin/maa`、`~/.local/bin/codex-local`。maa 安装时默认开启当前容器用户的 Codex 全局 YOLO；菜单可关闭并恢复原来的两项设置。

## Models

菜单“安装 / 登记新模型”支持：

- Ollama 官方模型：输入名称/tag，使用原生 `pull`。
- Ollama 本地 GGUF：输入模型名称与已有 GGUF 路径，原生导入。
- llama.cpp HF GGUF：输入仓库标识和**精确文件名**，缺一不可。
- llama.cpp 本地 GGUF：登记已有文件。

例如：

```text
HF repository: unsloth/Qwen3-0.6B-GGUF
GGUF filename: Qwen3-0.6B-Q4_K_M.gguf
```

HF 页面网址不是仓库标识。子目录必须包含在文件名里；分片 GGUF 填第一片，自动下载同一提交的完整分片集合。不搜索在线模型、不转换 Safetensors、不替换用户指定的量化版本。需要 HF 认证时可在运行安装命令的终端设置 `HF_TOKEN`；maa 不把令牌写入模型配置或服务文件。

下载完成不自动切换。进入“设置 AI 本地模型”，先选底座，再选其本地模型。Ollama 清单使用原生 API；读取清单或下载时会暂时暂停并恢复当前服务。llama.cpp 清单显示 maa 已下载或登记的 GGUF。

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

首次选择模型会打开默认配置，允许在加载前修改上下文和 KV；已有配置的模型直接恢复其配置。选择或应用配置会**立即重新加载**，同时保存下次容器启动的目标。失败时恢复之前的选择并尝试恢复服务，报告恢复结果。启动中断或容器重启不会把未验证的候选目标当作已成功目标。

“暂停”释放资源，但保留选择和自启动目标；“启动”恢复。空闲卸载保留底座服务，下一次请求由底座重新加载。`codex-local` 不在暂停状态下暗中启动模型。

## Codex

YOLO 只管理全局 `approval_policy = "never"` 和 `sandbox_mode = "danger-full-access"`。首次开启保存原值及存在状态，重复开启不覆盖备份；关闭恢复原值，原来没有的键删除。其他 TOML 配置保留。尊重 `CODEX_HOME`。

`codex-local` 使用专用 `maa-local.config.toml` profile，不覆盖普通 Codex 的模型设置，也不强制 YOLO 启动参数。模型与有效上下文同步，自动压缩阈值固定为有效上下文的 90%（262144 对应 235929）。推理档位按选定字符串传递，支持情况由客户端、底座和模型决定。

本地 Responses 接口适配普通/命名空间函数、custom 工具、工具结果回放、文本和 reasoning 流式事件。不能通过 codex-local 的模型/provider 参数绕开当前选择。

maa **不写入或覆盖 `web_search` 配置**。本地接口没有 OpenAI 托管搜索实现，因此不把 Codex 默认声明的托管搜索转交给模型；状态标明该能力不可用。已有 MCP 搜索函数仍可传递。Ollama 登录不会自动完成 Codex 搜索接入。本版不安装搜索 MCP。

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

完整安装及小模型验证会修改当前选择，请在**新建的专用临时 mas 容器**运行：

```bash
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/test/test.sh | bash
```

入口下载同版本测试包，运行 portable/PTY 检查与两个小模型的原生接口、Codex、暂停恢复及失败回滚检查，保存 JSON 报告，最后暂停模型。大模型、MTP 实际速度和全 GPU 装载仍需使用自己的模型验收。已核验范围见 [IMPLEMENTED.md](IMPLEMENTED.md)，开发说明见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

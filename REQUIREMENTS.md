# my-ai-agent Requirements — 0.1.1 test

用户于 2026-10-06 确认最终方案并授权开发及发布 0.1.1 test。自动压缩比例首版固定 90%，不添加未确认的比例修改入口。实现及验证见 IMPLEMENTED.md。

## Scope

安装在 mas 容器内，不修改宿主 mas。支持 Ollama 和 llama.cpp 共存，不包含 vLLM。提供官方一键安装、内联菜单 maa、专用本地入口 codex-local。项目安装默认开启 Codex 全局 YOLO。底座可以分开安装，但 maa 管理的运行服务同时只有一个底座/模型。

官方命令：
- Ollama: curl -fsSL https://ollama.com/install.sh | sh
- llama.cpp: curl -LsSf https://llama.app/install.sh | sh
- Codex: curl -fsSL https://chatgpt.com/codex/install.sh | sh

菜单沿用 mas 内联操作，方向键循环、Enter/右键确认、Esc/左键返回；文本左右键编辑、Esc 取消；主菜单退出、子菜单返回。支持安装、登记模型、设置本地模型、修改配置、暂停/启动、YOLO 设置和状态。CLI 提供帮助、版本、结构化状态、非交互参数和可靠退出码。

## Models

不实现在线搜索。Ollama 官方模型使用用户输入的完整名称/tag，通过原生 pull 下载，以原生 list/API 为本地清单；允许本地 GGUF 原生导入。llama.cpp 使用 HF 仓库 publisher/repository 加精确 GGUF 相对路径，两项均必填，对应 -hf/-hff；允许登记已有本地 GGUF，缓存复用。不替换量化版本、不转换 Safetensors。各底座内部存储独立，本地 GGUF 是可选文件来源。名字错误、认证、网络、磁盘、架构不支持保留准确诊断。

配置以底座和准确模型身份为唯一键，同时保存底座和 codex-local 配置。首次选择用默认值打开配置程序，允许在首次加载之前调整；取消不改变当前目标。再次选择恢复持久配置。

## Lifecycle

选择立即停止原底座、应用目标配置、启动并核验目标模型及有效上下文、同步 codex-local，然后提交当前/下次自启动目标。失败保留原选择并尝试恢复原服务，明确报告恢复结果。容器启动自动启动保存目标；暂停释放资源但保留目标，手动启动恢复，没有单独停用状态。官方安装器的默认服务不能留下第二个自动启动目标。

## Backend configuration

| Key | Default | Menu/input |
| --- | --- | --- |
| context | 262144 tokens | positive integer |
| kv | q8_0, same K/V | f16 / q8_0 / q4_0 |
| flash_attention | on | on / off, no auto |
| fit | on | on / off |
| reserve_mib | 0 | nonnegative integer |
| keep_alive | 5m | 5m / 10m / 30m / -1 |
| mtp | on when model/backend supports it | on / off, unsupported unavailable |
| mtp_kv | follow | follow / f16 / q8_0 / q4_0 |
| GPU placement | prefer full GPU, model preset then backend preset | none |
| sampling | model preset then backend preset | none |
| template | model preset then backend preset | none |
| service address | model preset then backend preset | none |
| MTP candidates | native/backend-specific below | none |

未列出的参数沿用原生行为。全 GPU 是优先目标，不虚报实际加载；不增加 CPU/GPU 分层放置入口。主 KV 和 draft KV 均 K/V 联动；draft 默认跟随，单独覆盖后保留，恢复 follow 重新联动。失败或不支持的参数不能显示为已生效。保留原模型采样预设和模板。

Ollama 使用 num_ctx、OLLAMA_KV_CACHE_TYPE、显式 Flash Attention、LLAMA_ARG_FIT/FIT_TARGET、KEEP_ALIVE 和实际支持的 draft KV。MTP 开启沿用有效正数 draft_num_predict，否则内部 4；关闭为 0。通过真实运行器和模型检测支持，不以名称猜测。使用原生运行元数据核验实际上下文。

llama.cpp 配置 context、main K/V、flash attention、fit、reserve、sleep idle 和 draft KV；MTP 为 draft-mtp / none，不覆盖 spec-draft-n-max 或相关环境变量。5m/10m/30m 映射 300/600/1800 秒，-1 禁用空闲卸载。通过原生服务元数据核验实际上下文。

接口适配固定一个本地 agent 推理槽，保证 llama.cpp 的上下文设置对应单次会话，而非被默认多个 slot 平分。Codex 默认声明的 OpenAI 托管 web_search 不具备本地实现时，不向原生模型声明该能力；仍不写入或覆盖 web_search 配置，状态明确标注 hosted_web_search=false。普通函数及已有 MCP 搜索函数保留。

## Codex global YOLO

只管理全局 approval_policy="never"、sandbox_mode="danger-full-access"，尊重 CODEX_HOME。首次开启持久保存每个键原来是否存在和原值；重复开启不覆盖备份。关闭时恢复原值或删除原来不存在的键，保留无关 TOML，不假设系统默认值。恢复跨重启有效。codex-local 继承全局设置，不使用强制 YOLO 参数或权限 profile 覆盖。

## codex-local

| Key | Behavior |
| --- | --- |
| model | actual active model ID |
| model_provider | dedicated local provider |
| base_url | actual local endpoint |
| wire_api | responses, compatibility verified |
| requires_openai_auth | false |
| model_context_window | effective backend context, no independent input |
| model_auto_compact_token_limit | floor(context * 90 / 100), fixed |
| model_reasoning_effort | omitted by default, fixed choices below |
| web_search | do not write/override |

推理档位：默认不覆盖 / none / minimal / low / medium / high / xhigh / max / ultra。保存和传递原值，不按模型删选项、不暗中转换，原生支持决定忽略或失败。上下文改变同步压缩阈值，262144 对应 235929。专用 profile 保留普通 codex 设置。底座必须实际支持 Responses 流式输出/工具调用，原生协议需要适配时使用本地适配器并核验语义。Ollama 搜索需另行接入，本版本不包含 MCP 搜索集成。

## Acceptance and publication

1. 在独立 mas 容器核验官方安装、完整打包和公共入口，不修改宿主开发环境。
2. 核验单一运行底座、立即切换、失败恢复、暂停/启动和重启后的保存目标。
3. 核验原生模型下载、本地清单、错误输入和真实诊断。
4. 核验默认值、配置持久化、KV follow/override、MTP 支持检测、实际上下文；无候选长度入口。
5. 核验 YOLO 两键恢复、重复开启、无关 TOML 保留、跨进程备份。
6. 核验本地 Responses 对话、流式、工具调用及 context/90% 同步。
7. PTY 验证导航、输入编辑、窄终端、取消和终端恢复；结构化输出无控制码。
8. 可重现构建、校验和、包边界、安装版本；不可变 v0.1.1 GitHub prerelease，回下载比较字节。stable 等待用户验收。
9. IMPLEMENTED.md 区分 portable/native/fault-injected/user-reported 证据，不宣称未实测的大模型/GPU/MTP 结果。

## Official references

- https://ollama.com/download/linux
- https://docs.ollama.com/faq
- https://github.com/ollama/ollama/blob/main/llm/llama_server.go
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://learn.chatgpt.com/docs/codex/cli
- https://learn.chatgpt.com/docs/config-file/config-reference
- https://learn.chatgpt.com/docs/config-file/config-advanced

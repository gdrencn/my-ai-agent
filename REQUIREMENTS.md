# my-ai-agent Requirements — 0.1.3 test

用户于 2026-10-06 确认最终方案并授权开发及发布 0.1.1 test。自动压缩比例首版固定 90%，不添加未确认的比例修改入口。实现及验证见 IMPLEMENTED.md。

## 0.1.3 menu and model status

用户确认菜单、配置项呈现、模型名称及状态采集方案，并授权执行。另发 0.1.3 test，保留已发布资产。

1. 主菜单顶部显示“当前模型”和“运行状态”，实际运行、空闲卸载、暂停、读取失败明确区分。主菜单按本地模型管理、Codex 配置、Codex 全局设置、安装底座 / Codex CLI、关于、退出组织。各子菜单保留返回及选中位置。
2. 本地模型管理包括设置本地模型（立即切换）、安装 / 登记新模型、模型配置、当前模型状态、暂停当前模型、启动当前模型、返回。Codex 配置单独显示推理强度、跟随实际有效上下文的只读上下文大小、固定 90% 的只读自动压缩阈值及应用修改。Codex 全局设置只有“YOLO 模式：状态”和返回；进入 YOLO 后才选择开启或关闭（恢复原设置）。主菜单不提供原始“当前状态与配置”；完整结构化配置保留 maa status，原生日志保留 maa logs。
3. 配置项使用“标题：当前值 / 状态”，标题正常颜色，数值、枚举、跟随、默认为青色，开启及运行中绿色，关闭、暂停、不可用灰色；错误明确显示。进入选项后才修改，保留当前默认选择、取消、待应用修改提示。顶部状态和只读字段使用相同规则，窄终端、无颜色模式与重定向保留文字。通用 CLI/TUI 规范不包含项目名称或业务需求。
4. Codex profile、模型目录 slug、Responses 返回 model、公开 /v1/models 使用原模型名称；内部登记 key 和 Ollama 配置别名仅用于管理和上游路由。基础身份说明使用原模型名称，不向模型提供无意义的管理 ID，不修改原模型模板或采样预设。原配置、驻留复用和失败恢复保持有效。
5. “当前模型状态”使用项目自己的格式，顺序为底座、当前模型、运行状态、GPU 装载与分项、上下文统计、刷新 / 返回。Ollama 独立使用 /api/ps 与自己的当前加载日志，llama.cpp 独立使用 /props 与自己的当前加载日志；各自采集后归一化呈现。查询不生成 token、不读取会唤醒的 /slots、不启停底座、不改变模型选择。
6. 可展示模型层 GPU 装载、权重、主 KV、RS、计算与输出缓冲区，按实际 GPU / 系统内存位置分类。MTP 额外 KV 与计算按初始化阶段分别统计，共享部分不得重复求和；不支持显示不可用，未开启显示未启用。删除独立 MTP 权重及实时 KV token 占用字段。合计仅称“已识别显存分配合计”，不等同完整进程显存。CPU_Mapped 是映射量，不冒充实际 RSS；CUDA_Host 不属于显存。
7. 原生分配日志只统计当前服务启动和当前实际加载；排除 fit 试算、重试及旧模型、旧配置、旧启动日志，重复缓冲区记录更新而非累加。休眠、卸载、暂停、加载中不展示旧分配值；无法确认的值显示未取得，绝不把缺失填成 0。采集应有超时和读取上限，原生诊断仍通过 maa logs 可见。
8. 整卡总量、已用、可用及驱动预留按实际 NVIDIA 驱动读取，多个 GPU 分别列出；接口不可用时给出原因，不用总量减已用伪造可用量，不从整卡占用推导当前模型完整占用。
9. 上下文统计包含实际有效容量、最近一次完成的 maa Responses 请求输入 token 数及容量比例、最近一次生成 token 数、统计时间。只保存身份、计数及时间，不保存对话。缺失 usage、失败及中断不伪造统计，切换 / 重新加载后旧统计不冒充当前模型统计；不累加重放历史，不称为实时 KV 使用量。
10. 验收包括两个底座的独立只读查询、当前启动与重载隔离、fit / MTP / RS / Host 分配分类、未知与异常数据、成功 / 失败请求统计、颜色与真实 PTY 的菜单导航和返回、两种原生底座的状态与 Codex 名称、暂停 / 卸载时查询无唤醒、打包一致性。原生 MTP 若未实测，应在实现文档明确说明，不能把源码或日志夹具核验写成实际推理验收。

## 0.1.2 corrections

用户授权修复 0.1.1 验收中收集的问题；新版本发布为独立 0.1.2 test，不替换 0.1.1。

1. codex-local 专用模型目录只包含当前模型，内部 ID 与真实请求匹配，显示原模型名称。目录同步实际上下文及已实现的文本/函数工具能力，不声明图像或托管搜索支持；推理档位仍保持既定选项，不保证原生支持。切换失败恢复先前 profile 和模型目录，普通 Codex 配置保持独立。真实 Codex /model 验证只显示本地模型且不再出现 fallback metadata 警告。
2. codex-local 对已驻留且配置一致的目标只做检查，不重复创建 Ollama 别名或请求加载。空闲卸载后按原配置唤醒，并更新实际上下文；暂停目标仍拒绝暗中启动。核验官方显式 embedded/no-daemon 模式，若支持则用于专用 profile 以避免自动回退提示，不过滤 Codex 诊断。
3. 所有可能阻塞的管理操作立即反馈，终端中同一行每秒刷新阶段和累计耗时，结束显示成功、失败或中断及总耗时。失败恢复纳入同一计时流程。原生安装/下载进度保持可见，与计时行不互相覆盖。非终端输出不包含控制码，不污染 CLI stdout JSON；非终端不打印重复计时行。
4. 模型选择页面按底座显示文案，llama.cpp 不显示 Ollama 暂停提示。
5. 原生测试无论成功或失败都清理自己创建的坏 GGUF、登记记录和失败配置；保留用户模型与已选择的正常测试模型，报告明确记录清理结果。真实测试还核验已驻留启动不会重建别名、空闲卸载唤醒、两条启动提示和实际 /model 界面。

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
| model | original active model name; adapter uses the exact native routing ID |
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
8. 可重现构建、校验和、包边界、安装版本；不可变 v0.1.3 GitHub prerelease，回下载比较字节。stable 等待用户验收。
9. IMPLEMENTED.md 区分 portable/native/fault-injected/user-reported 证据，不宣称未实测的大模型/GPU/MTP 结果。

## Official references

- https://ollama.com/download/linux
- https://docs.ollama.com/faq
- https://github.com/ollama/ollama/blob/main/llm/llama_server.go
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://learn.chatgpt.com/docs/codex/cli
- https://learn.chatgpt.com/docs/config-file/config-reference
- https://learn.chatgpt.com/docs/config-file/config-advanced

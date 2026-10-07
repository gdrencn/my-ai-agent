# my-ai-agent Requirements — 0.1.8 test

## 0.1.8 recovery, inventory and upgrade boundaries

用户授权修复本轮审查确认的七项问题，保留一次性工具和原生直连结构。

1. 显式启动、维护恢复和切换回滚使用明确的已提交目标；仅当前切换事务允许启动其候选。强制中断留下的 target.json 不得优先于 selected.json，显式启动应修复临时目标并重新核验未完成的事务，不能启动未提交的底座。失败仍保留已提交选择。
2. Ollama 启动就绪必须来自当前原生 API 的驻留模型及有效上下文；历史 runtime.json 只作已保存状态展示，不能代替本次启动验收。空模型清单、未加载或无有效上下文继续等待；明确服务失败保留诊断。
3. 模型管理维护的恢复范围覆盖最初停止原底座的阶段。Ctrl+C 在停止、维护操作或恢复阶段发生时保留中断退出码 130；恢复失败附带准确诊断，不将原中断转换成普通失败。原服务恢复只使用已提交目标。
4. 产品安装先核验原生服务、maa/codex-local 命令归属和 Codex TOML，再迁移或替换归档。拒绝输入不留下归档、入口或旧服务变更；归档及入口写入阶段异常恢复已有归档、入口和 Codex 配置，首次安装不遗留半成品入口。入口提交之后再迁移或安装官方依赖；后续失败保留可用的管理入口和准确诊断，官方依赖安装器自身的变更不承诺回滚。
5. Ollama 原生清单保留完整本地模型来源和准确身份。未变化的 digest 复用已登记详情，只读取新增/变化的详情；原配置备份每次清单只读取一次。注册变更合并为一次原子保存，清单未变化不写文件；安装后的目标查询不重新读取无关模型详情。配置后 digest 与原权重身份分别处理，不能复用已变化模型的旧详情。
6. 模型选项保留当前选择和短名称；同名 GGUF 在选项中补充可区分的目录信息。焦点详情显示完整 HF 仓库、文件相对路径和已固定 revision；本地文件显示完整路径。窄终端换行保留区别，不仅依赖 basename。
7. 全局 YOLO 默认开启仅用于首次安装产品。后续产品更新、重装和 Codex CLI 更新不改变用户当前开关或已有恢复备份；安装前已存在的旧产品/状态按升级处理。显式 YOLO 开启/关闭仍只修改或恢复原有两键。

验收覆盖隔离故障模拟、真实 PTY、可重现配对包和独立 mas 容器的原生流程。测试套件为工具验收显式设置 YOLO 基线，不假定升级前用户已开启；该操作归属测试而非安装器。另发不可变 0.1.8 test，不替换已有资产；stable 仍需用户验收。

## 0.1.7 selective lifecycle and interaction improvements

用户授权完成本轮代码及交互优化，保留一次性工具和原生直连结构。

1. Codex 全局 YOLO 和 codex-local 推理强度修改不启停、重载或唤醒底座；后者使用已核验的上下文同步 profile，并保存每模型设置。暂停状态保持暂停。未变化的配置应用不重载。CLI 与菜单共享这些规则。
2. 重载仅用于更换底座/模型、改变底座参数、更新当前底座程序及修复未核验的运行配置。启动已运行模型复用当前实例；空闲卸载时仅唤醒模型；暂停时启动保存的原生配置。升级 Codex CLI 不重载底座。失败恢复原配置及状态。
3. 配置页面只读项及不可用的 MTP 项无激活行为；Enter/右键不结束或重新创建菜单。选择底座/模型默认定位当前项并标注当前模型；长模型名提供当前焦点的完整文件名与来源信息。只读上下文在暂停/空闲时标注已保存的核验值，不冒充实时观察。
4. 读取当前托管、已运行 Ollama 的清单直接使用原生 API，不暂停/恢复服务。需要临时原生服务时保留单底座协调及恢复；无效名称/文件在启停之前拒绝。
5. HF/local GGUF 注册记录全部分片的身份；缺失、替换或变化在停止当前模型之前拒绝。旧分片记录无完整身份时要求重新登记。缓存按下载目标独立加锁，修复损坏或不完整的缓存文件；HF 下载/文件扫描不持有全局管理锁。运行中的托管 Ollama 下载不持有全局管理锁；显式暂停/切换可中断该原生传输，保留准确诊断和原生重试能力。需要临时 Ollama 服务的操作仍协调服务生命周期。
6. Ctrl+C 回滚后保持中断退出码 130及中断提示，明确报告恢复成功或失败；不能转换成普通失败。
7. 主菜单采用轻量只读状态，不解析分配日志或查询整卡显存。完整状态页合并不可用请求统计说明，保留结构化 CLI 字段。进度与所有外部命令输出协调换行，诊断不被覆盖。
8. 测试中预期失败不混同产品故障；通过检查的详细诊断保存到报告，控制台显示检查结果和报告路径。真实失败保留完整诊断。核验 portable/PTY、配对包及独立 mas 容器的原生路径；另发不可变 0.1.7 test，stable 仍需用户验收。

## 0.1.6 immediate Codex entry after official installation

修正 0.1.5 用户验收发现的 `exec: codex: not found`：官方安装器写入用户 `~/.local/bin` 后，不要求测试进程或通过绝对路径运行的 codex-local 先重开终端。独立启动脚本在自己的进程中将 `$HOME/.local/bin` 加入 PATH，保留继承的 PATH，再直接 exec 官方 Codex；不调用 maa、不启动后台服务、不修改父 shell 或全局配置。验证当前 PATH 不含用户安装目录、HOME 路径含空格、正常参数及 exec 进程身份；完整原生验收必须以不含用户安装目录的 PATH 启动 Codex 子进程。另发不可变 0.1.6 test，不覆盖 0.1.5 资产。

## 0.1.4 standalone tools and native direct connections

用户明确确认并授权：maa 只能是一次性安装、配置、检查与切换工具；底座和 Codex 的运行不依赖 maa。以下条款取代此前涉及 maa 常驻服务、协议适配器和启动期 maa 调用的要求。

1. 删除 maa.service 和 maa 的对话协议中转。任何自启动命令只能执行官方底座程序与原生配置，不能调用 maa、其 Python 模块或归档；不能把中转或守护进程换名保留。
2. Ollama 与 llama.cpp 分别维护自身原生启动配置和对应 Codex 直连配置，按底座和模型身份保存。切换由 maa 停止旧底座、应用新配置、启动与检查、同步独立启动脚本后退出。只启用一个底座的自启动，暂停保留其自启动选择，失败恢复旧配置及运行状态。
3. codex-local 是独立 shell 启动脚本：直接 exec 官方 Codex，使用 maa 已保存的配置和模型目录；不得调用 maa、启动 maa 父进程、检查 maa 状态、改写配置或转发请求。移除 maa 归档后，已配置的底座自启动与 codex-local 仍须工作。
4. 两条直连路径分别核验原生 Responses、流式正文及推理、工具调用与结果回放、真实 Codex 执行和 /model。不得以存在 HTTP 路由替代实际验证；协议缺口如不能用官方配置解决，明确说明并讨论，不能重新增加 maa 服务。
5. 保留配置默认值、KV 跟随、YOLO 两键恢复、菜单颜色与操作计时。主菜单“Codex 配置”管理 YOLO，排在“codex-local 配置”之前；后者管理本地推理与上下文配置。HF 仍保留仓库和精确文件两项。
6. 原生状态查询分别读取底座 API 和当前原生日志，日志与启动身份由原生服务确定。删除对 maa 对话中转收据的依赖；直连后无法可靠取得的统计显示未取得并说明来源，不能伪造旧数据或引入后台监听。
7. 从旧版本迁移时仅清理可核验属于 maa 的旧服务和入口；保留模型、每模型配置、普通 Codex 配置和 YOLO 恢复备份。迁移失败给出明确诊断，不覆盖不属于项目的文件或服务。
8. 在独立 mas 容器验证安装、原生直连、立即切换、回滚、暂停与重启自启动、maa 运行依赖移除、独立启动脚本、终端导航和可重现打包。记录原生限制；当前另发不可变 0.1.7 test，stable 仍需用户验收。

自动压缩比例固定 90%，不添加未确认的比例修改入口。旧版本的需求与实现记录保留在 Git 历史和 validation 收据中。实现及验证见 IMPLEMENTED.md。

## Scope

安装在 mas 容器内，不修改宿主 mas。支持 Ollama 和 llama.cpp 共存，不包含 vLLM。提供官方一键安装、内联菜单 maa、专用本地入口 codex-local。项目首次安装默认开启 Codex 全局 YOLO，后续更新保留用户选择。底座可以分开安装，但 maa 管理的运行服务同时只有一个底座/模型。

官方命令：
- Ollama: curl -fsSL https://ollama.com/install.sh | sh
- llama.cpp: curl -LsSf https://llama.app/install.sh | sh
- Codex: curl -fsSL https://chatgpt.com/codex/install.sh | sh

菜单沿用 mas 内联操作，方向键循环、Enter/右键确认、Esc/左键返回；文本左右键编辑、Esc 取消；主菜单退出、子菜单返回。支持安装、登记模型、设置本地模型、修改配置、暂停/启动、YOLO 设置和状态。CLI 提供帮助、版本、结构化状态、非交互参数和可靠退出码。

## Models

不实现在线搜索。Ollama 官方模型使用用户输入的完整名称/tag，通过原生 pull 下载，以原生 list/API 为本地清单；允许本地 GGUF 原生导入。llama.cpp 使用 HF 仓库 publisher/repository 加精确 GGUF 相对路径，两项均必填，对应 -hf/-hff；允许登记已有本地 GGUF，缓存复用。不替换量化版本、不转换 Safetensors。各底座内部存储独立，本地 GGUF 是可选文件来源。名字错误、认证、网络、磁盘、架构不支持保留准确诊断。

配置以底座和准确模型身份为唯一键，同时保存底座和 codex-local 配置。首次选择用默认值打开配置程序，允许在首次加载之前调整；取消不改变当前目标。再次选择恢复持久配置。

## Lifecycle

更换底座/模型或修改底座参数时，立即停止原底座、应用目标配置、启动并核验目标模型及有效上下文、同步 codex-local，然后提交当前/下次自启动目标。相同配置复用已运行实例；Codex 配置仅保存对应设置，不重载或唤醒底座。失败保留原选择并恢复原生配置、自启动设置、Ollama 原名称参数和 Codex profile，尝试恢复原服务并明确报告结果。候选核验前关闭自启动；强制杀进程或掉电可能保留关闭状态，重新 maa start 核验保存目标，不自动启动未验收候选。容器启动自动启动保存目标；暂停释放资源但保留目标，手动启动恢复，没有单独停用状态。官方安装器的默认服务不能留下第二个自动启动目标。

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

llama.cpp 固定一个本地 agent 推理槽，保证 llama.cpp 的上下文设置对应单次会话，而非被默认多个 slot 平分。不写入或覆盖 web_search 配置，不安装搜索 MCP，不拦截请求。托管搜索、命名空间工具和推理档位的支持取决于对应原生接口，不能宣称所有 Codex 工具都受支持。专用目录不声明原生接口无法完整支持的 custom/freeform apply_patch；文件编辑保留普通 shell 工具。

## Codex global YOLO

只管理全局 approval_policy="never"、sandbox_mode="danger-full-access"，尊重 CODEX_HOME。首次开启持久保存每个键原来是否存在和原值；重复开启不覆盖备份。关闭时恢复原值或删除原来不存在的键，保留无关 TOML，不假设系统默认值。恢复跨重启有效。codex-local 继承全局设置，不使用强制 YOLO 参数或权限 profile 覆盖。

## codex-local

| Key | Behavior |
| --- | --- |
| model | original native active model name |
| model_provider | dedicated local provider |
| base_url | actual local endpoint |
| wire_api | responses, compatibility verified |
| requires_openai_auth | false |
| model_context_window | effective backend context, no independent input |
| model_auto_compact_token_limit | floor(context * 90 / 100), fixed |
| model_reasoning_effort | omitted by default, fixed choices below |
| web_search | do not write/override |

推理档位：默认不覆盖 / none / minimal / low / medium / high / xhigh / max / ultra。保存和传递原值，不按模型删选项、不暗中转换，原生支持决定忽略或失败。上下文改变同步压缩阈值，262144 对应 235929。专用 profile 保留普通 codex 设置。底座必须实际支持 Responses 流式输出、普通函数工具调用和回放，分别写入正确的原生地址。不能增加协议中转。Ollama 搜索需另行接入，本版本不包含 MCP 搜索集成。

## Acceptance and publication

1. 在独立 mas 容器核验官方安装、完整打包和公共入口，不修改宿主开发环境。
2. 核验单一运行底座、立即切换、失败恢复、暂停/启动和重启后的保存目标。
3. 核验原生模型下载、本地清单、错误输入和真实诊断。
4. 核验默认值、配置持久化、KV follow/override、MTP 支持检测、实际上下文；无候选长度入口。
5. 核验 YOLO 两键恢复、重复开启、无关 TOML 保留、跨进程备份。
6. 核验本地 Responses 对话、流式、工具调用及 context/90% 同步。
7. PTY 验证导航、输入编辑、窄终端、取消和终端恢复；结构化输出无控制码。
8. 可重现构建、校验和、包边界、安装版本；不可变 v0.1.8 GitHub prerelease，回下载比较字节。stable 等待用户验收。
9. IMPLEMENTED.md 区分 portable/native/fault-injected/user-reported 证据，不宣称未实测的大模型/GPU/MTP 结果。

## Official references

- https://ollama.com/download/linux
- https://docs.ollama.com/faq
- https://github.com/ollama/ollama/blob/main/llm/llama_server.go
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://learn.chatgpt.com/docs/codex/cli
- https://learn.chatgpt.com/docs/config-file/config-reference
- https://learn.chatgpt.com/docs/config-file/config-advanced

## Menu and status contract

主菜单依次为本地模型管理、Codex 配置、codex-local 配置、安装底座 / Codex CLI、关于 my-ai-agent、退出。顶部为当前模型、运行状态。

- 本地模型管理：设置本地模型、安装 / 登记新模型、模型配置、当前模型状态、暂停当前模型、启动当前模型、返回。
- Codex 配置：YOLO 模式与当前状态、返回；进入 YOLO 后选择开启、关闭（恢复原设置）、返回。
- codex-local 配置：推理强度、只读有效上下文、只读 90% 压缩阈值、应用修改、返回。
- 安装菜单：全部安装、Ollama、llama.cpp、Codex CLI、返回。
- 关于显示当前 maa 版本和返回。

标题正常颜色，数值/枚举/default/follow 青色，开启和运行中绿色，关闭/暂停/不可用灰色，错误明确显示。进入选项才修改；保留当前选择，取消不提交，显示待应用变更。无颜色及窄终端保留文字。

状态按底座分别采集：Ollama /api/ps，llama.cpp /props。只读查询不推理、不调用会唤醒的 /slots、不启停服务。当前原生启动 InvocationID 与当前真实加载日志决定分配记录；日志最多读取 4 MiB，排除 fit 试算与旧加载，重复记录替换，不重复合计。

依次显示底座、模型、状态、GPU 层装载、权重、主 KV、RS、计算/输出缓冲区、MTP 额外 KV/计算、已识别显存分配合计、整卡显存、有效上下文、请求统计未取得原因、刷新/返回。CPU_Mapped 为映射而非 RSS，CUDA_Host 为系统内存，MTP 共享 KV 不重复计数。没有 MTP 显示不可用；独立 MTP 权重和实时 KV token 占用不提供。分项不能冒充完整进程占用。NVIDIA 驱动分别读取总量/已用/可用/预留；未知保留未知，不填 0 或推导可用量。暂停/空闲/加载不展示旧分项。

0.1.5 修正 portable 测试对目录枚举顺序的错误依赖；产品行为沿用 0.1.4。不得覆盖已发布 0.1.4 的资产。

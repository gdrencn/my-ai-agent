# Basic chat connectors — 0.2.1 test

本阶段验证 IM 收发链路。收到允许用户的私聊文本后，只回复可配置的固定测试文字；没有 Codex 接入、AI 回复、会话管理、聊天命令解释、群聊或媒体处理。`/new`、`/resume` 不作为管理命令执行。

## Installation and runtime

在 mas 容器内升级到 0.2.1 test 后，进入 `maa → 聊天接入`。可先选择“安装 / 更新连接器程序”，也可在添加第一个账号时自动安装。产品升级本身不会建立账号或首次开启服务。

Maa 是一次性管理工具。连接器是独立的 `connectors.pyz`，由 `maa-connectors-<UID>.service` 运行；每个已开启账号有自己的接收线程。它不导入 Maa 管理模块、不运行 Codex、不使用模型底座，也不代理 Codex 请求。服务的启动命令不调用 Maa 程序。

| Platform | Limit | Official access |
| --- | --- | --- |
| Telegram | 多个不同的机器人 | BotFather 建立机器人，Bot API Token，长轮询 |
| WhatsApp | 一个个人 Agent | WhatsApp 的 Agents 功能，Agent API key，长轮询 |
| 微信 | 一个账号 | 腾讯公开 iLink 接口，扫码授权，长轮询 |

没有需要统一安装的三个官方 Python 包。实现直接调用各家的 HTTPS API，使用 Python 标准库；不安装 OpenClaw、WhatsApp Web 模拟客户端或微信非官方登录框架。平台权限、地区和账号资格以官方当前开放情况为准。

## Menu

```text
聊天接入
  全部接入开关：开启 / 关闭
  Telegram：N 个接入
  WhatsApp：N 个接入
  微信：N 个接入
  安装 / 更新连接器程序：已安装 / 未安装
  刷新
  导出全部接入
  导入接入备份
  卸载聊天连接器
  返回
```

平台页列出账号及连接状态；Telegram 可继续添加，另两家已有账号时不提供第二个添加入口。账号页显示平台、名称、平台账号、连接状态、收发计数、结果不确定计数、最后收发时间及脱敏诊断，下面提供：

```text
接入开关：开启 / 关闭
本地名称：当前名称
固定测试回复：当前文字
接入凭证：已设置
允许测试的用户：当前 ID / 未绑定    # Telegram
刷新
导出此接入
删除本地接入
返回
```

设置值在选项中显示并单独着色，进入后再修改。账号添加后保持关闭；单独开启会启用连接器自启动。单独关闭保留配置，其他账号继续运行。全部关闭把每个接入设为关闭，并停止服务及取消自启动；全部开启会开启所有已配置账号，Telegram 未绑定用户时拒绝开启。

## Telegram

1. 使用官方 [BotFather](https://core.telegram.org/bots/features#botfather) 创建测试机器人，复制 Token。每个机器人使用不同 Token，不要让其他程序同时对同一个机器人轮询。
2. 选择“Telegram → 添加接入”，输入本地名称和 Token。Token 输入显示星号；已有 webhook 的机器人会被拒绝，不会自动删除其 webhook。
3. 可直接输入允许测试的数字用户 ID；也可留空，添加后进入账号的“允许测试的用户 → 接收私聊消息并确认用户”。从自己的 Telegram 向该机器人发一条新的私聊文本，核对显示的发送者 ID 后确认。此时仅绑定，不自动开启。
4. 开启该接入，再发一条私聊文本，确认收到固定回复。重复上述流程可配置第二个 TG 测试机器人。关闭其中一个，确认另一个继续工作。

只允许绑定的用户私聊文本。其他用户、群聊和媒体不会触发测试回复。Bot API 的 update offset 和已处理 ID 保存在本地，重启后继续使用。

## WhatsApp

使用官方个人 Agent Platform，接口为 `https://api.whatsapp.com/agent/v1`。此处不是需要公网 webhook 的 WhatsApp Business Cloud API，也不接管普通 WhatsApp 账号登录。官方说明见 [Agent Platform manual](https://www.whatsapp.com/developer/WhatsApp-Agent-Platform-Developer-Manual.pdf) 和 [Agents 帮助](https://faq.whatsapp.com/1050934623978152)。

1. 在已开放 Agents 功能的 WhatsApp 账号中创建个人 Agent，取得它的 API key。如果没有入口，本工具不能替账号开通。
2. 进入“WhatsApp → 添加接入”，输入名称和 API key。添加时保持关闭，不把凭证写进命令参数。
3. 开启接入，从创建者账号向 Agent 发新的文本，确认固定回复。接口限制创建者使用；本地同时记住首次收到的创建者 ID，后续只接受该用户。

收发使用 Bearer 凭证及官方长轮询。保留完整整数游标，204 空响应不清空游标；轮询至少间隔 4.1 秒，发送至少间隔 5.1 秒。认证失败显示连接异常，更新凭证后重新建立接收线程。不要用同一 key 同时启动其他轮询客户端。

## WeChat

实现依据腾讯发布的 [iLink 协议与客户端](https://github.com/Tencent/openclaw-weixin/blob/main/docs/protocol_zh_CN.md)，自行实现 HTTP 接入，不安装 OpenClaw。公开资料说明的是当前客户端行为，不是完整服务端契约，独立实现还需真实账号验收。

1. 进入“微信 → 添加接入”，输入名称并取得官方授权二维码内容。
2. 容器已安装 `qrencode` 时会在终端渲染二维码；否则显示官方返回的授权链接或二维码内容。`qrencode` 只是可选的显示工具，不参与登录协议。
3. 用手机微信完成扫码确认；若官方要求配对码，在菜单中输入手机显示的值。过期或受限时取消后重新授权。成功后保存官方返回的 bot token、用户 ID 和 API 地址，默认保持关闭。
4. 开启后，从授权用户发送文本，确认固定回复。回复使用当前入站消息的 context token；没有该令牌时不猜测发送。

授权过期显示异常并按公开客户端规则退避一小时；可通过“接入凭证”重新扫码，保留本地接入 ID。二维码已有绑定但未返回新凭证时，不覆盖已有配置。只接受 `weixin.qq.com` 及其子域的 HTTPS 重定向；不会根据备份访问任意服务器。

## CLI

命令与菜单使用相同管理实现，不重新加载底座或修改 Codex 配置。CLI 成功结果为 stdout JSON，等待与授权提示写入 stderr。Token 参数只接受文件路径或不回显的交互输入。

```bash
maa im install
maa im status
maa im add telegram --name tg-test --token-file /absolute/private/tg-token --owner-id 123456789
maa im add whatsapp --name wa-test --token-file /absolute/private/wa-key
maa im wechat --name wx-test
maa im bind CONNECTION_ID
maa im config CONNECTION_ID --owner-id 123456789
maa im config CONNECTION_ID --reply '消息收发测试成功。'
maa im on CONNECTION_ID
maa im off CONNECTION_ID
maa im off
maa im export /absolute/private/connectors.json
maa im export /absolute/private/one.json --id CONNECTION_ID
maa im delete CONNECTION_ID --yes
maa im import /absolute/private/connectors.json
maa im uninstall --yes
```

`bind` 只返回候选 ID，不自动接受；确认后用 `config --owner-id` 保存。`on` 不带 ID 表示开启全部，`off` 不带 ID 表示关闭全部。更新 Token 使用 `config ID --token-file /absolute/path`，微信重新授权使用 `wechat --id ID`。`export --overwrite` 显式允许覆盖已有文件。

## Persistence, closing and recovery

| Resource | Default location |
| --- | --- |
| 配置、凭证、游标、去重、状态 | `~/.local/state/my-ai-agent-im`，支持 `MAA_IM_HOME` / `XDG_STATE_HOME` |
| 独立程序 | `~/.local/share/my-ai-agent/connectors.pyz` |
| 原生服务 | `/etc/systemd/system/maa-connectors-<UID>.service` |

目录权限 `0700`，状态及导出备份 `0600`。备份包含明文凭证，应保存在用户指定的私有位置，不提交 GitHub。状态与日志不保存入站聊天正文；固定测试回复属于配置，备份包含它。

导入保留接入 ID、凭证、游标及去重记录，全部导入项保持关闭。相同 ID、重复平台账号、数量超限、非法字段或 API 地址会被拒绝，不覆盖已有账号。恢复同一份备份前先明确删除原接入。凭证被官方撤销或过期时必须重新填写或扫码，本地备份不能恢复官方权限。

关闭会取消请求及重试，并等待该连接退出确认；关闭全部还停止整个服务。关闭保留配置。删除只清理选定连接；卸载先停止并禁用所属服务，再删除所属程序、服务文件及全部本地接入状态。外来文件、被修改的程序/服务或额外 service drop-in 会阻止自动清理，需要先处理归属冲突。

本地删除不调用远端解绑、撤销 Token 或删除机器人。以后可重新添加，或导入关闭前导出的备份。回退旧 Maa 前先导出需要保留的接入，再运行 `maa im uninstall --yes`，按 [固定 0.1.9 回退步骤](ROLLBACK.md) 恢复旧管理工具。

## Delivery and acceptance limits

接收时先持久化已处理消息 ID，再尝试回复。发送结果不确定时记录计数，不盲目重发；明确的限流或暂不可用可以有限重试。这避免重启后重复发送，但崩溃发生在标记与实际发送之间可能漏掉回复，不承诺恰好一次投递。去重窗口保留最近 2000 个 ID，平台保留期限也限制离线补收。

本地官方协议模拟覆盖鉴权、收发格式、游标、去重、隔离、异常和取消；容器验证安装、独立运行、关闭、备份、删除、导入和卸载。这些测试不使用真实平台凭证，不代替官方账号验收。

用户验收请分别配置 TG、WhatsApp、微信各一个，TG 可增加第二个；检查固定回复、单独关闭、容器重启、关闭全部、导出/删除/导入后重新开启及最终卸载。真实账号尚未验收前，本版本仅为 test，不发布 stable。

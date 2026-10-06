"""Centralized first-release Chinese UI text; native diagnostics are retained."""
MESSAGES = {
    'menu_keys': '↑/↓ 选择 · Enter/→ 确定 · Esc/← {action}',
    'menu_multi_keys': '↑/↓ 选择 · Space 勾选 · Enter 确定 · Esc {action}',
    'menu_cancel': '取消', 'menu_back': '返回', 'menu_exit': '退出',
    'input_keys': '←/→ 编辑 · Enter 提交 · Esc 取消',
    'choice_no': '否', 'choice_yes': '是',
    'title': 'my-ai-agent', 'install': '安装底座 / Codex CLI',
    'add': '安装 / 登记新模型', 'select': '设置 AI 本地模型（立即切换）',
    'configure': '修改当前模型配置', 'pause': '暂停当前模型，释放资源',
    'start': '启动当前模型', 'yolo': 'Codex 全局 YOLO 设置',
    'status': '当前状态与配置', 'about': '关于 my-ai-agent',
    'back': '返回', 'exit': '退出', 'cancelled': '已取消。',
    'done': '操作完成。', 'empty': '没有本地可选模型，请先安装 / 登记新模型。',
    'backend': '请选择底座', 'source': '请选择模型来源',
    'official': 'Ollama 官方模型', 'hf': 'Hugging Face GGUF', 'local': '本地 GGUF 文件',
    'model_name': 'Ollama 模型名称（例如 qwen3:0.6b）：',
    'repo': 'HF 仓库（publisher/repository）：',
    'filename': '精确 GGUF 相对路径（包含 .gguf，不含网址）：',
    'path': '已有 GGUF 文件的绝对路径：',
    'context': '上下文大小', 'kv': '主模型 KV 格式',
    'flash_attention': 'Flash Attention', 'fit': '自动适配显存',
    'reserve_mib': '显存预留（MiB）', 'keep_alive': '模型空闲驻留时间',
    'mtp': 'MTP', 'mtp_kv': 'MTP KV 格式', 'reasoning': 'Codex 推理强度',
    'on': '开启', 'off': '关闭', 'follow': '跟随主模型', 'default': '默认（不显式覆盖）',
    'apply': '应用修改（立即重新加载）', 'unavailable': '不可用：模型没有可核验的 MTP 权重',
    'integer': '{label}：请输入{constraint}整数；留空保留 {value}。',
    'positive': '正', 'nonnegative': '非负',
    'no_target': '尚未选择模型。', 'running': '运行中', 'stopped': '已暂停 / 停止',
    'current': '当前目标：{backend} / {model} / {status}',
    'model_title': '请选择本地模型；读取 Ollama 清单时会暂时暂停并恢复当前服务。',
    'result': '结果', 'error': '错误：{error}',
}


def t(key, **values):
    return MESSAGES[key].format(**values)

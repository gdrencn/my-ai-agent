# my-ai-agent project instructions

- 默认中文沟通。先讨论后执行；用户已授权的开发及 test 发布持续完成，stable 需用户验收授权。
- 需求以 REQUIREMENTS.md 为准，实现及实测证据以 IMPLEMENTED.md 为准，先核验后更新实现文档。
- CLI 与菜单复用 Manager、settings、codex、service 模块；菜单控件复用 mas 衍生的 Screen，不重复业务逻辑。
- 不在宿主安装底座、修改宿主 Codex 或全局工作规范。原生验证使用独立 mas 临时容器。
- 产品和测试包版本一致。已验收的 stable tag、release 和资产保持不变，确保可回退。同一轮尚未交付验收的 test 开发、自检和修复使用同一版本，可同步更新该 test 的 tag、配对包、元数据及校验清单；完成核验后再交付测试命令，不因轮内修复另增版本。构建及检查见 docs/DEVELOPMENT.md。
- 不将本机凭据、全局 Codex 数据、用户模型、临时目录或未核验的实测结论提交仓库。

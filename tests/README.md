## 测试分层架构
### Layer 1: 纯 Unit（无浏览器）
- 数据结构测试：SessionInfo、ProviderConfig
- 逻辑测试：配置解析、路径处理
- 可以完全使用 mock
### Layer 2: 浏览器模拟测试（可选）
- ActionExecutor 的配置解析、选择器构建
- 状态检查逻辑
- 使用 Playwright 的 mock API
### Layer 3: 原子化功能测试（真实浏览器）
- test_sidebar_expand.py - 侧边栏展开
- test_session_create.py - 创建会话
- test_session_rename.py - 重命名会话
- test_session_delete.py - 删除会话
- test_session_switch.py - 切换会话
- test_message_send.py - 发送消息

### 目录结构
```PlainText
tests/
├── unit/
│   ├── test_session.py
│   ├── test_adapters.py
│   ├── test_manager.py
│   ├── test_action_executor.py
│   └── providers/
│       ├── deepseek/
│       │   └── test_deepseek_config.py    # DeepSeek 配置单元测试
│       └── qwen/
│           └── test_qwen_config.py        # Qwen 配置单元测试
│
└── integration/
    ├── test_login.py
    ├── test_sidebar.py
    ├── test_session_create.py
    ├── ...
    └── providers/
        ├── deepseek/
        │   ├── test_deepseek_login.py     # DeepSeek 登录测试
        │   └── test_deepseek_sidebar.py   # DeepSeek 侧边栏测试
        └── qwen/
            └── test_qwen_login.py         # Qwen 登录测试
```
# 集成测试

本目录包含 WebLLM 框架的集成测试，需要实际浏览器环境和登录状态。

**重要**：所有 pytest 命令都从项目根目录运行，测试文件位于 `tests/integration/` 目录下。

## 测试结构

### 通用测试基础设施

`conftest.py` 提供了与 provider 无关的通用 fixture，实现了测试代码的高度内聚：


### Layer 3: 原子化测试（浏览器测试）

所有通用测试均与具体 provider 解耦，通过 fixture 自动适配不同 provider。

| 测试文件 | 测试内容 |
|---------|---------|
| `test_login.py` | 通用登录检测和等待 |
| `test_sidebar.py` | 通用侧边栏展开/收起状态检测 |
| `test_sidebar_session.py` | 侧边栏会话管理测试 |


## 前置条件

### 1. 安装 Python 依赖

```powershell
pip install pytest pytest-asyncio pytest-mock
pip install playwright>=1.60.0
playwright install chromium
```

### 2. 首次运行需要手动登录

- 运行测试时浏览器会以非无头模式打开
- 在浏览器中手动登录 DeepSeek 网站
- 登录成功后关闭浏览器
- 后续运行会自动使用持久化登录状态

### 3. 工作目录

所有命令都从项目根目录运行：

## 运行命令

### Layer 3 通用原子化测试

所有通用测试均支持通过 `--provider` 参数指定测试目标（默认 provider 为 deepseek）：

```powershell
# 登录检测测试
pytest tests/integration/test_login.py -v -s

# 创建会话测试
pytest tests/integration/test_session_create.py -v -s

# 重命名会话测试
pytest tests/integration/test_session_rename.py -v -s

# 切换会话测试
pytest tests/integration/test_session_switch.py -v -s

# 删除会话测试
pytest tests/integration/test_session_delete.py -v -s

# 发送消息测试
pytest tests/integration/test_message.py -v -s

# 指定 provider 运行测试
pytest tests/integration/test_login.py -v -s --provider deepseek
pytest tests/integration/test_login.py -v -s --provider qwen

# 按顺序运行多个测试
pytest tests/integration/test_login.py tests/integration/test_sidebar.py tests/integration/test_session_create.py -v -s
```

### DeepSeek Provider 特定测试

```powershell
# DeepSeek 所有集成测试
pytest tests/integration/providers/deepseek/ -v -s

# DeepSeek 登录测试
pytest tests/integration/providers/deepseek/test_deepseek_login.py -v -s

# DeepSeek 侧边栏测试
pytest tests/integration/providers/deepseek/test_deepseek_sidebar.py -v -s

# DeepSeek 会话搜索测试
pytest tests/integration/providers/deepseek/test_deepseek_search.py -v -s

# DeepSeek 模式选择测试
pytest tests/integration/providers/deepseek/test_deepseek_modes.py -v -s

# DeepSeek 开关切换测试
pytest tests/integration/providers/deepseek/test_deepseek_toggles.py -v -s

# DeepSeek 文件上传测试
pytest tests/integration/providers/deepseek/test_deepseek_upload.py -v -s

# 运行单个具体测试函数
pytest tests/integration/providers/deepseek/test_deepseek_login.py::test_deepseek_login_indicator_config -v -s
```

### Qwen Provider 特定测试

```powershell
# Qwen 所有集成测试
pytest tests/integration/providers/qwen/ -v -s

# Qwen 登录测试
pytest tests/integration/providers/qwen/test_qwen_login.py -v -s
```

### 完整流程测试

```powershell
# 单适配器完整流程测试
python tests/integration/test_integration.py --adapter deepseek
python tests/integration/test_integration.py --adapter qwen

# 会话管理综合测试
python tests/integration/test_session.py --adapter deepseek
python tests/integration/test_session.py --adapter qwen
```

## 原子化测试说明

### 通用测试（与 Provider 解耦）

通用测试通过 `conftest.py` 提供的 fixture 实现与具体 provider 的完全解耦，具有以下特点：

1. **测试代码内聚性高**：login、create、delete 等测试逻辑不依赖具体 provider 实现
2. **可复用性强**：同一测试用例可测试不同 provider
3. **易于扩展**：新增 provider 时无需修改通用测试代码

#### test_login.py（通用登录检测）
- 测试登录指示器配置有效性（检查 `user_logged_in` 状态配置）
- 测试登录指示器选择器能定位到元素
- 测试通过 executor 检查登录状态
- 测试登录等待超时处理

#### test_sidebar.py（通用侧边栏操作）
- 测试侧边栏初始化状态
- 测试通过 executor 检查状态
- 测试 ensure 展开功能
- 测试展开/收起切换

#### test_session_create.py（通用会话创建）
- 测试创建第一个会话
- 测试创建多个会话
- 测试创建后缓存更新
- 测试特殊字符处理
- 测试重复标签处理
- 测试使用指定模式创建会话

#### test_session_rename.py（通用会话重命名）
- 测试重命名当前会话
- 测试重命名后切换
- 验证重命名相关动作配置

#### test_session_switch.py（通用会话切换）
- 测试在多个会话间切换
- 测试切换到已存在会话
- 测试切换到不存在会话（自动创建）
- 测试切换更新最后活跃时间

#### test_session_delete.py（通用会话删除）
- 测试从本地缓存删除会话
- 测试删除当前会话后自动切换
- 测试删除所有会话
- 测试删除不存在的会话

### Provider 特定测试

#### DeepSeek

**providers/deepseek/test_deepseek_login.py**
- 测试 DeepSeek 登录指示器配置（包含 avatar 选择器检查）
- 测试 DeepSeek 登录状态检测
- 测试 DeepSeek 页面登录相关元素
- 测试 DeepSeek 侧边栏状态配置

**providers/deepseek/test_deepseek_sidebar.py**
- 测试 DeepSeek 展开按钮配置（包含 _4f3769f 类检查）
- 测试 DeepSeek 收起按钮配置（包含 _7d1f5e2 类检查）
- 测试 DeepSeek 侧边栏初始化状态
- 测试 DeepSeek 侧边栏切换功能
- 测试 DeepSeek 确保侧边栏展开功能

**providers/deepseek/test_deepseek_search.py**
- 测试搜索动作配置存在（search_input、search_clear_btn）
- 测试会话搜索功能
- 测试空关键词搜索
- 测试搜索后清除功能
- 验证搜索输入框选择器配置

**providers/deepseek/test_deepseek_modes.py**
- 测试模式配置存在
- 测试模式选择动作配置（select_quick_mode、select_expert_mode、select_vision_mode）
- 测试获取能力声明（get_capabilities）
- 测试获取默认模式（_get_default_mode）
- 测试获取模式功能列表（_get_mode_features）
- 测试获取模式开关列表（_get_mode_toggles）
- 测试功能支持检查（_is_feature_supported）
- 测试开关可用性检查（_is_toggle_available）
- 测试使用指定模式创建会话

**providers/deepseek/test_deepseek_toggles.py**
- 测试开关动作配置存在（toggle_deep_think、toggle_internet_search）
- 测试深度思考开关配置
- 测试智能搜索开关配置
- 验证 set_toggle 方法存在及签名
- 验证能力声明中的开关配置
- 验证开关状态指示器配置

**providers/deepseek/test_deepseek_upload.py**
- 测试上传动作配置存在（upload_file_quick、upload_file_vision）
- 测试上传动作配置结构（action=upload）
- 验证文件上传选择器配置
- 验证视图模式上传选择器配置
- 验证能力声明中的上传功能配置
- 验证 upload_file 方法存在及签名
- 测试临时文件创建

#### Qwen

**providers/qwen/test_qwen_login.py**
- 测试 Qwen 登录指示器配置
- 测试 Qwen 登录状态检测
- 测试 Qwen 侧边栏状态配置

## 注意事项

- 所有命令都从项目根目录（`f:\python_programs\myagent`）运行
- 测试文件路径：`tests/integration/*.py`
- 需要保持网络连接
- 首次运行需要人工干预登录
- 测试时间取决于网络和模型响应速度
- 请遵守各服务商的使用条款
- 建议按顺序运行：login -> sidebar -> session 操作
- 集成测试会打开真实浏览器，建议使用非 headless 模式（不加 --headless）

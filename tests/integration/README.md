# 集成测试

本目录包含 WebActor 框架的集成测试，需要实际浏览器环境。

**重要**：所有 pytest 命令都从项目根目录运行，测试文件位于 `tests/integration/` 目录下。

## 测试结构

### 通用测试基础设施

`conftest.py` 提供了与 provider 无关的通用 fixture，实现了测试代码的高度内聚：

- `page_operator`：创建 PageOperator 实例，启动浏览器
- `logged_in_operator`：已登录的 PageOperator 实例

### 测试文件

| 测试文件 | 测试内容 |
|---------|---------|
| `test_login.py` | 通用登录检测和等待 |
| `test_sidebar.py` | 通用侧边栏展开/收起状态检测 |
| `test_sidebar_sessions.py` | 侧边栏会话管理测试 |

## 前置条件

### 1. 安装 Python 依赖

```powershell
pip install pytest pytest-asyncio pytest-mock
pip install playwright>=1.60.0
pip install pyyaml
playwright install chromium
```

### 2. 首次运行需要手动登录

- 运行测试时浏览器会以非无头模式打开
- 在浏览器中手动登录目标网站
- 登录成功后关闭浏览器
- 后续运行会自动使用持久化登录状态

### 3. 工作目录

所有命令都从项目根目录运行。

## 运行命令

### 运行所有集成测试

```powershell
pytest tests/integration/ -v -s
```

### 运行单个测试文件

```powershell
# 登录检测测试
pytest tests/integration/test_login.py -v -s

# 侧边栏测试
pytest tests/integration/test_sidebar.py -v -s

# 侧边栏会话测试
pytest tests/integration/test_sidebar_sessions.py -v -s
```

### 运行单个测试函数

```powershell
pytest tests/integration/test_login.py::test_login_indicator_config -v -s
```

## 测试说明

### test_login.py（通用登录检测）

- `test_login_indicator_config`：测试登录指示器配置有效性（检查 `user_logged_in` 状态配置）

### test_sidebar.py（通用侧边栏操作）

- 测试侧边栏初始化状态
- 测试通过 executor 检查状态
- 测试 ensure 展开功能
- 测试展开/收起切换

### test_sidebar_sessions.py（会话管理）

- 测试会话列表获取
- 测试会话创建
- 测试会话切换

## 注意事项

- 所有命令都从项目根目录运行
- 测试文件路径：`tests/integration/*.py`
- 需要保持网络连接
- 首次运行需要人工干预登录
- 测试时间取决于网络和页面响应速度
- 集成测试会打开真实浏览器，建议使用非 headless 模式（不加 --headless）

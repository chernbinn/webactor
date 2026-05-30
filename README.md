# WebActor

WebActor 是一个基于 Playwright 的配置驱动型浏览器自动化框架，通过 YAML 配置文件定义页面动作和状态，实现高度可复用的浏览器操作能力。

## 核心特性

- **配置驱动**：通过 YAML 配置文件定义所有页面动作和状态检查逻辑
- **原子化操作**：提供可组合的原子化动作，支持多种定位策略
- **持久化会话**：支持浏览器上下文持久化，自动复用登录状态
- **异步架构**：基于 asyncio 的异步设计，支持高并发操作
- **业务无关**：核心框架不依赖具体业务逻辑，通过配置适配不同网站

## 项目结构

```
webactor/
├── src/
│   └── page/
│       ├── __init__.py
│       ├── page_operator.py      # 浏览器生命周期管理
│       ├── action_executor.py    # 动作执行引擎
│       └── exceptions.py         # 异常定义
├── config/
│   └── deepseek_actions.yaml     # DeepSeek 网站动作配置
├── tests/
│   ├── unit/                     # 单元测试
│   └── integration/               # 集成测试
├── pyproject.toml
└── pytest.ini
```

## 快速开始

### 1. 创建配置文件

在 `config/` 目录下创建 YAML 配置文件：

```yaml
provider: example
base_url: https://example.com
login_required: true
user_data_dir: browser_profiles/example

global:
  min_interval_sec: 1
  slow_mo: 150
  typing_min: 80
  typing_max: 200

capabilities:
  modes:
    - name: default
      default: true

actions:
  is_logged_in:
    action_type: any_visible
    locate:
      - text: "退出登录"

  click_login_button:
    action_type: click
    locate:
      - text: "登录"
    wait_after: 500
```

### 2. 使用 PageOperator

```python
import asyncio
from page.page_operator import PageOperator

async def main():
    operator = PageOperator(
        config_path="config/example_actions.yaml",
        headless=False
    )

    await operator.start()

    # 执行动作
    result = await operator.execute("click_login_button")

    # 检查状态
    is_logged_in = await operator.execute("is_logged_in")

    await operator.close()

asyncio.run(main())
```

## 配置说明

### 全局配置 (global)

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `min_interval_sec` | float | 1 | 操作最小间隔（秒） |
| `slow_mo` | int | 150 | Playwright slow_mo 参数 |
| `typing_min` | int | 80 | 模拟打字最小速度（字符/秒） |
| `typing_max` | int | 200 | 模拟打字最大速度（字符/秒） |

### 动作定义 (actions)

每个动作包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `action_type` | string | 动作类型（click、type、any_visible 等） |
| `locate` | list | 定位策略列表，按优先级尝试 |
| `wait_after` | int | 动作执行后等待时间（毫秒） |
| `script` | string | JavaScript 脚本（用于 evaluate 类型动作） |

### 动作类型

| 动作类型 | 说明 |
|----------|------|
| `click` | 点击元素 |
| `type` | 输入文本 |
| `hover` | 鼠标悬停 |
| `any_visible` | 检查任意元素是否可见 |
| `all_visible` | 检查所有元素是否可见 |
| `any_exists` | 检查任意元素是否存在 |
| `evaluate` | 执行 JavaScript 脚本 |

### 定位策略

```yaml
locate:
  - text: "按钮文本"           # 通过文本内容定位
  - css: ".class-name"         # 通过 CSS 选择器定位
  - placeholder: "输入框占位符" # 通过占位符文本定位
  - role: button               # 通过 ARIA 角色定位
    name: "按钮名称"
```

### 能力声明 (capabilities)

```yaml
capabilities:
  modes:
    - name: quick
      default: true
      features:
        - name: upload
          action: "upload_file_quick"
      toggles:
        - name: deep_think
          action: "toggle_deep_think"
          default: false
```

## 异常处理

框架定义了以下异常类：

| 异常类 | 说明 |
|--------|------|
| `ElementNotFoundError` | 元素未找到 |
| `ActionTimeoutError` | 动作执行超时 |
| `ActionConfigError` | 动作配置错误 |
| `ConfigNotFoundException` | 配置文件不存在 |
| `ConfigLoadError` | 配置文件加载失败 |
| `LoginRequiredException` | 需要登录 |
| `SessionExpiredException` | 会话过期 |
| `QuotaExceededException` | 配额超限 |

## 单元测试执行

```powershell
# 运行所有测试
pytest tests/ -v

# 运行集成测试
pytest tests/integration/ -v -s

# 运行特定测试文件
pytest tests/integration/test_login.py -v -s
```

集成测试需要：
1. 安装 Playwright Chromium 浏览器
2. 测试以非 headless 模式运行（`-s` 参数）
3. 首次运行需要手动登录目标网站

## 许可证

MIT License

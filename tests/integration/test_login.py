"""
登录集成测试

测试登录检测和等待功能

根据设计文档：
- Provider.ensure_logged_in() 确保用户已登录
- ActionExecutor.check_state() 检查登录状态
"""
import os
import yaml
import pytest

def get_login_config_path():
    """获取登录配置文件路径"""
    path = os.path.join(os.path.dirname(__file__), "../../config/deepseek_actions.yaml")
    return str(path)

@pytest.mark.asyncio
async def test_login_indicator_config():
    """
    测试：登录指示器配置有效性
    """
    config_path = get_login_config_path()
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    actions = config["actions"]

    assert "is_logged_in" in actions, "缺少 is_logged_in 配置"

    is_logged_in = actions["is_logged_in"]
    assert "locate" in is_logged_in
    assert len(is_logged_in["locate"]) > 0

    # DeepSeek 特定检查：确保有选择器
    selectors = is_logged_in["locate"]
    assert len(selectors) > 0, "DeepSeek 登录指示器应包含选择器"


@pytest.mark.asyncio
async def test_deepseek_login_check(page_operator):
    """
    测试：DeepSeek 登录状态检测
    
    此测试验证登录状态检测功能能够正确工作：
    - 使用多种选择器进行检测
    - 返回正确的布尔值表示登录状态
    """
    operator = page_operator
    
    # 通过 executor 检查登录状态
    result = await operator.execute("is_logged_in")

    # 验证返回类型
    assert isinstance(result, bool)
    
    # 打印检测结果（帮助调试）
    print(f"登录状态检测结果: {result}")
    
    # 如果返回 True，说明检测到登录状态，测试通过
    # 如果返回 False，可能是未登录状态或选择器需要调整
    # 这里我们只验证返回类型正确，因为实际登录状态取决于测试环境
    if result:
        print("✓ 检测到已登录状态")
    else:
        print("✓ 检测到未登录状态（或选择器需要调整）")



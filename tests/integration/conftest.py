import os
import pytest

from page.page_operator import PageOperator

def get_login_config_path():
    """获取登录配置文件路径"""
    path = os.path.join(os.path.dirname(__file__), "../../config/deepseek_actions.yaml")
    return str(path)

# 不可以使用 module scope 因为 使用后在检测浏览器元素时会卡住
# @pytest.fixture(scope="module")
@pytest.fixture
async def page_operator():
    """创建登录 PageOperator 实例（模块级，只启动一次浏览器）"""
    operator = PageOperator(
        config_path=get_login_config_path(),
        headless=False
    )
    await operator.start()
    yield operator

    print("\n 按Enter键继续...")
    input()
    await operator.close()


@pytest.fixture
async def logged_in_operator(page_operator):
    """已登录的 PageOperator 实例（复用同一个浏览器）"""
    operator = page_operator
    
    print("\n" + "=" * 60)
    print("  请确保已登录，页面处于正常状态！")
    print("  准备好后按 Enter 键继续测试...")
    print("=" * 60 + "\n")
    
    return operator
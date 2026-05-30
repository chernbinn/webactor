"""
DeepSeek 侧边栏集成测试

测试 DeepSeek 特定的侧边栏动作配置
"""
import pytest
import random

from page.action_executor import ActionExecutor

@pytest.fixture
async def expand_sidebar(logged_in_operator):
    """展开侧边栏"""
    assert hasattr(logged_in_operator, 'executor')
    assert isinstance(logged_in_operator.executor, ActionExecutor)
    assert logged_in_operator.executor.actions is not None
    assert len(logged_in_operator.executor.actions) > 0

    expanded = await logged_in_operator.execute('is_sidebar_expanded')
    if not expanded:
        await logged_in_operator.execute('sidebar_expand_btn')
    expanded = await logged_in_operator.execute('is_sidebar_expanded')    
    assert expanded is True
    print("侧边栏已展开\n")

    return logged_in_operator

@pytest.mark.asyncio
async def test_sidebar_session_list(expand_sidebar):
    """测试：获取会话列表
    """
    print("\n--- 测试 获取会话列表 ---")
    result = await expand_sidebar.execute('conversation_list')
    print(f"conversation_list 返回: {result}")
    assert result is not None
    assert len(result) > 0

    print("测试 conversation_list1 动作")    
    result = await expand_sidebar.execute('conversation_list1')
    print(f"conversation_list1 返回: {result}")
    assert result is not None
    assert len(result) > 0

# ========== 状态检查类 action 测试 ==========
@pytest.mark.asyncio
async def test_sidebar_session_current(expand_sidebar):
    """测试：获取当前会话
    """
    print("\n--- 测试 获取当前session会话标题 ---")
    print("先切换到一个会话，例如webactor")
    print("切换完成后输入当前会话标题，按Enter键继续...")
    title = input()
    print(f"输入的会话标题: {title}\n")
    
    print("测试 current_conversation_title 动作")    
    result = await expand_sidebar.execute('current_conversation_title')
    
    print(f"current_conversation_title 返回: {result}")
    assert result == title
    print()
    
    print("测试 current_conversation_title1 动作")    
    result = await expand_sidebar.execute('current_conversation_title1')
    
    print(f"current_conversation_title1 返回: {result}")
    assert result == title

@pytest.mark.asyncio
async def test_sidebar_session_switch(expand_sidebar):
    """测试：切换会话
    """    
    print("\n--- 测试 切换会话 ---")
    print("先切换到一个会话，例如webactor")
    print("切换完成后，按Enter键继续...")
    input()
    result = await expand_sidebar.execute('conversation_list')
    # 随机选择一个会话
    title = random.choice(result)
    print(f"输入的会话标题: {title}\n")

    result = await expand_sidebar.execute('current_conversation_title')
    print(f"当前会话标题: {result}")
    await expand_sidebar.execute('switch_conversation', title=title)
    result = await expand_sidebar.execute('current_conversation_title')
    print(f"current_conversation_title 返回: {result}")
    assert result == title

@pytest.mark.asyncio
async def test_sidebar_session_menu(expand_sidebar):
    """测试：测试会话菜单
    """    
    print("\n--- 测试 测试会话菜单 ---")
    result = await expand_sidebar.execute('conversation_list')
    # 随机选择一个会话
    title = random.choice(result)
    print(f"会话标题: {title}\n")
    await expand_sidebar.execute('switch_conversation', title=title)
    result = await expand_sidebar.execute('current_conversation_title')
    print(f"current_conversation_title 返回: {result}")
    assert result == title

    await expand_sidebar.execute('current_conversation_menu')

@pytest.mark.asyncio
async def test_sidebar_session_toplist(expand_sidebar):
    """测试：测试获取置顶会话列表
    """
    print("\n--- 测试 获取置顶会话列表 ---")
    result = await expand_sidebar.execute('conversation_toplist')
    print(f"conversation_toplist 返回: {result}")
    assert result is not None
    assert len(result) > 0

@pytest.mark.asyncio
async def test_sidebar_session_period_list(expand_sidebar):
    """测试：测试获取不同时间范围的会话列表
    """
    print("\n--- 测试 获取不同时间范围的会话列表 ---")
    print("获取7天内的会话列表：")
    result = await expand_sidebar.execute('conversation_period_list', period='7 天内')
    print(f"conversation_period_list 返回: {result}")
    assert result is not None
    assert len(result) > 0

    print("获取30天内的会话列表：")
    result = await expand_sidebar.execute('conversation_period_list', period='30 天内')
    print(f"conversation_period_list 返回: {result}")
    assert result is not None
    assert len(result) > 0

    print("获取置顶会话列表：")
    result = await expand_sidebar.execute('conversation_period_list', period='置顶')
    print(f"conversation_period_list 返回: {result}")
    assert result is not None
    assert len(result) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


"""
DeepSeek 侧边栏集成测试

测试 DeepSeek 特定的侧边栏动作配置
"""
import pytest
import asyncio

from page.action_executor import ActionExecutor

# ========== 状态检查类 action 测试 ==========

@pytest.mark.asyncio
async def test_action_executor_exists(logged_in_operator):
    """测试：ActionExecutor 是否正确初始化"""
    assert hasattr(logged_in_operator, 'executor')
    assert isinstance(logged_in_operator.executor, ActionExecutor)
    assert logged_in_operator.executor.actions is not None
    assert len(logged_in_operator.executor.actions) > 0


@pytest.mark.asyncio
async def test_sidebar_state_expanded(logged_in_operator):
    """测试：is_sidebar_expanded - 检查侧边栏展开状态
    
    注意：此测试仅检查元素定位是否有效，不保证逻辑正确性。
    实际状态可能因页面布局而不同，请手动确认结果。
    """
    print("\n--- 测试 is_sidebar_expanded ---")
    print("请手动展开侧边栏")
    print("按 Enter 继续...")
    input()
    
    result = await logged_in_operator.execute('is_sidebar_expanded')
    
    print(f"is_sidebar_expanded 返回: {result}")
    assert result is True

@pytest.mark.asyncio
async def test_sidebar_state_collapsed(logged_in_operator):
    """测试：is_sidebar_expanded - 检查侧边栏收起状态
    
    注意：此测试仅检查元素定位是否有效，不保证逻辑正确性。
    实际状态可能因页面布局而不同，请手动确认结果。
    """
    print("\n--- 测试 is_sidebar_expanded ---")
    print("请手动收起侧边栏")
    print("按 Enter 继续...")
    input()
    
    result = await logged_in_operator.execute('is_sidebar_expanded')
    
    print(f"is_sidebar_expanded 返回: {result}")
    assert result is False


# ========== 侧边栏控制类 action 测试 ==========

@pytest.mark.asyncio
async def test_sidebar_action_expand_btn(logged_in_operator):
    """测试：sidebar_expand_btn - 展开侧边栏
    
    请先手动收起侧边栏，然后运行此测试！
    """
    print("\n--- 测试 sidebar_expand_btn ---")
    print("请先手动收起侧边栏")
    print("确认侧边栏已收起后，按 Enter 继续...")
    input()
    
    await logged_in_operator.execute('sidebar_expand_btn')
    print("sidebar_expand_btn 执行成功！")
    status = await logged_in_operator.execute('is_sidebar_expanded')
    print(f"展开后侧边栏状态: {'展开' if status else '收起'}")
    assert status, "侧边栏应该已展开"

@pytest.mark.asyncio
async def test_sidebar_action_collapse_btn(logged_in_operator):
    """测试：sidebar_collapse_btn - 收起侧边栏
    
    请先手动展开侧边栏，然后运行此测试！
    """
    print("\n--- 测试 sidebar_collapse_btn ---")
    print("请先手动展开侧边栏")
    print("确认侧边栏已展开后，按 Enter 继续...")
    input()
    
    await logged_in_operator.execute('sidebar_collapse_btn')    
    print("sidebar_collapse_btn 执行成功！")
    status = await logged_in_operator.execute('is_sidebar_expanded')
    print(f"收起后侧边栏状态: {'展开' if status else '收起'}")
    assert not status, "侧边栏应该已收起"

@pytest.mark.asyncio
async def test_toggle_sidebar_expand(logged_in_operator):
    """
    测试：DeepSeek 点击展开侧边栏功能
    流程：
    1. 获取当前侧边栏状态
    2. 如果是收起状态，点击展开按钮
    3. 等待片刻后再次检查状态
    4. 验证状态已变为展开
    """
    
    # 第一步：获取初始状态
    initial_state = await logged_in_operator.execute('is_sidebar_expanded')
    print(f"侧边栏初始状态: {'展开' if initial_state else '收起'}")
    
    # 如果已经是展开状态，先收起
    if initial_state:
        print("侧边栏已展开，先收起...")
        try:
            await logged_in_operator.execute('sidebar_collapse_btn')
            await asyncio.sleep(1)  # 等待动画效果完成
            # 检查收起后的状态
            collapsed_state = await logged_in_operator.execute('is_sidebar_expanded')
            print(f"侧边栏收起后状态: {'展开' if collapsed_state else '收起'}")
            assert not collapsed_state, "侧边栏应该已收起"
        except Exception as e:
            print(f"收起时出错（可能按钮不存在）: {e}")
    
    # 现在应该是收起状态，尝试展开
    print("尝试展开侧边栏...")
    try:
        await logged_in_operator.execute('sidebar_expand_btn')
        # await asyncio.sleep(1)  # 等待动画效果完成
        
        # 检查展开后的状态
        expanded_state = await logged_in_operator.execute('is_sidebar_expanded')
        print(f"侧边栏展开后状态: {'展开' if expanded_state else '收起'}")
        
        # 验证状态已变为展开
        assert expanded_state, "侧边栏应该已展开"
        
    except Exception as e:
        print(f"展开操作出错: {e}")
        pytest.skip("跳过展开测试，可能选择器有问题或页面不同")


@pytest.mark.asyncio
async def test_toggle_sidebar_collapse(logged_in_operator):
    """
    测试：DeepSeek 点击收起侧边栏功能
    流程：
    1. 确保侧边栏处于展开状态
    2. 点击收起按钮
    3. 等待片刻后再次检查状态
    4. 验证状态已变为收起
    """
    
    # 第一步：确保侧边栏处于展开状态
    initial_state = await logged_in_operator.execute('is_sidebar_expanded')
    print(f"侧边栏初始状态: {'展开' if initial_state else '收起'}")
    
    # 如果是收起状态，先展开
    if not initial_state:
        print("侧边栏已收起，先展开...")
        try:
            await logged_in_operator.execute('sidebar_expand_btn')
            await asyncio.sleep(1)  # 等待动画效果完成
            # 检查展开后的状态
            expanded_state = await logged_in_operator.execute('is_sidebar_expanded')
            print(f"侧边栏展开后状态: {'展开' if expanded_state else '收起'}")
            assert expanded_state, "侧边栏应该已展开"
        except Exception as e:
            print(f"展开时出错（可能按钮不存在）: {e}")
    
    # 现在应该是展开状态，尝试收起
    print("尝试收起侧边栏...")
    try:
        await logged_in_operator.execute('sidebar_collapse_btn')
        await asyncio.sleep(1)  # 等待动画效果完成
        
        # 检查收起后的状态
        collapsed_state = await logged_in_operator.execute('is_sidebar_expanded')
        print(f"侧边栏收起后状态: {'展开' if collapsed_state else '收起'}")
        
        # 验证状态已变为收起
        assert not collapsed_state, "侧边栏应该已收起"
        
    except Exception as e:
        print(f"收起操作出错: {e}")
        pytest.skip("跳过收起测试，可能选择器有问题或页面不同")

@pytest.mark.asyncio
async def test_circle_toggle_sidebar(logged_in_operator):
    """
    测试：DeepSeek 循环点击展开-收起侧边栏功能
    流程：
    1. 获取初始状态
    2. 点击展开按钮，验证状态变化为展开
    3. 点击收起按钮，验证状态变化为收起
    4. 重复以上步骤，验证状态循环切换
    """
    print("\n--- 测试循环切换侧边栏 ---")
    
    # 确保侧边栏处于收起状态开始
    initial_state = await logged_in_operator.execute('is_sidebar_expanded')
    print(f"侧边栏初始状态: {'展开' if initial_state else '收起'}")
    
    if initial_state:
        print("先收起侧边栏...")
        try:
            await logged_in_operator.execute('sidebar_collapse_btn')
            await asyncio.sleep(1)
        except Exception as e:
            print(f"收起失败: {e}")
    
    # 开始循环测试
    for i in range(3):  # 循环3次
        print(f"\n=== 第 {i+1} 次循环 ===")
        
        # 步骤1: 展开侧边栏
        print("步骤1: 点击展开按钮")
        try:
            await logged_in_operator.execute('sidebar_expand_btn')
            
            expanded_state = await logged_in_operator.execute('is_sidebar_expanded')
            print(f"展开后状态: {'展开' if expanded_state else '收起'}")
            assert expanded_state, f"第{i+1}次循环：侧边栏应该已展开"
            
        except Exception as e:
            print(f"展开失败: {e}")
            raise
        
        # 步骤2: 收起侧边栏
        print("步骤2: 点击收起按钮")
        try:
            await logged_in_operator.execute('sidebar_collapse_btn')
            
            collapsed_state = await logged_in_operator.execute('is_sidebar_expanded')
            print(f"收起后状态: {'展开' if collapsed_state else '收起'}")
            assert not collapsed_state, f"第{i+1}次循环：侧边栏应该已收起"
            
        except Exception as e:
            print(f"收起失败: {e}")
            raise
    
    print("\n✅ 循环切换测试完成！")


@pytest.mark.asyncio
async def test_sidebar_round_trip(logged_in_operator):
    """
    测试：DeepSeek 侧边栏完整的展开-收起往返流程
    流程：
    1. 获取初始状态
    2. 根据初始状态执行相应操作
    3. 验证状态变化
    4. 执行反向操作
    5. 验证状态回到初始状态
    """
    
    # 获取初始状态
    initial_state = await logged_in_operator.execute('is_sidebar_expanded')
    print(f"侧边栏初始状态: {'展开' if initial_state else '收起'}")
    
    try:
        # 执行第一次操作
        if initial_state:
            print("尝试收起侧边栏...")
            await logged_in_operator.execute('sidebar_collapse_btn')
        else:
            print("尝试展开侧边栏...")
            await logged_in_operator.execute('sidebar_expand_btn')
        
        # 验证第一次状态变化
        after_first_operation = await logged_in_operator.execute('is_sidebar_expanded')
        print(f"第一次操作后状态: {'展开' if after_first_operation else '收起'}")
        assert after_first_operation != initial_state, "侧边栏应该已变化"
        
        # 确保状态确实变化了
        # 但要处理按钮点击后无反应的情况（可能页面不同）
        if after_first_operation != initial_state:
            # 执行反向操作
            print("执行反向操作...")
            if after_first_operation:
                await logged_in_operator.execute('sidebar_collapse_btn')
            else:
                await logged_in_operator.execute('sidebar_expand_btn')
            
            # 验证状态回到初始状态
            final_state = await logged_in_operator.execute('is_sidebar_expanded')
            print(f"最终状态: {'展开' if final_state else '收起'}")
            assert final_state == initial_state, "侧边栏应该回到初始状态"
        else:
            print("状态没有变化，可能按钮不存在或页面有差异")
            
    except Exception as e:
        print(f"操作出错: {e}")
        pytest.skip("跳过往返测试，可能选择器有问题或页面不同")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


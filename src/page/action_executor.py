import random
import time
import json
import asyncio
from typing import Optional, Dict, Any, List, Union
from playwright.async_api import Page, Locator
from .exceptions import ElementNotFoundError, ActionConfigError

DEFAULT_CONFIG_CONFIG = {
    "min_interval_sec": 1,
    "typing_max": 200,
    "typing_min": 80,
}

class ActionExecutor:

    _CHECKMODES = (
        "any_visible",
        "any_exists",
        "all_visible",
        "all_hidden",
        "any_hidden",
        "all_exists",
    )
    _EXTRACTORS = (
        "text",
        "value",
        "attribute",
        "inner_text",
        "inner_html",
        "outer_text",
        "outer_html",
    )
    """
    动作执行器 - 配置驱动的页面操作引擎
    根据 YAML 配置执行原子化的页面操作，支持多策略容错定位
    
    能力模型：
    - capabilities: 业务能力声明（模式、功能、开关）
    - actions: 原子动作定义
    """
    
    def __init__(self, page: Page, actions: dict, global_config: dict, capabilities: dict = None):
        """
        初始化 ActionExecutor
        """
        self.page = page
        self.global_config = global_config or {}
        self.actions = actions or {}
        self.capabilities = capabilities or {}
        
        # 操作时间跟踪
        self._last_action_time = 0
        self._last_message_time = 0
    
    def get_capabilities(self) -> dict:
        """
        返回提供者能力声明的原始字典
        
        Returns:
            capabilities 字典，包含 modes、toggles 等
        """
        return self.capabilities
    
    async def _wait_interval(self, is_message_action: bool = False) -> None:
        """
        等待操作间隔，确保操作频率符合全局配置
        
        Args:
            is_message_action: 是否是发送消息操作
        """
        now = time.time()
        # 普通操作间隔
        interval = self.global_config.get("min_interval_sec", DEFAULT_CONFIG_CONFIG["min_interval_sec"])
        elapsed = now - self._last_action_time
        
        if elapsed < interval:
            wait_time = interval - elapsed
            await asyncio.sleep(wait_time)
        
        # 更新时间戳
        if is_message_action:
            self._last_message_time = time.time()
        else:
            self._last_action_time = time.time()
    
    async def execute(self, action_name: str, **params) -> Any:
        """
        执行指定动作
        
        Args:
            action_name: 动作名称，对应配置中的 key
            **params: 动作参数，如 value, key 等
            
        Returns:
            操作结果，可能是文本内容、布尔值或元素列表
        """
        await self._wait_interval()
        action_def = self.actions.get(action_name)
        if not action_def:
            raise ActionConfigError(f"未找到动作定义: {action_name}")
        
        # 检查是否需要跳过
        skip_sel = action_def.get("skip_if_visible")
        if skip_sel:
            try:
                skip_el = await self.page.query_selector(skip_sel)
                if skip_el and await skip_el.is_visible():
                    return None
            except Exception:
                pass
        
        action_type = action_def.get("action_type", "click")
        print(f"executor-action: {action_name} ({action_type})")
        
        # 特殊处理：extract_list 不需要定位单个元素
        if action_type == "extract_list":
            return await self._execute_extract_list(action_def)
        
        # 特殊处理：状态检查类动作
        if action_type in self._CHECKMODES:
            # return await self._execute_state_check(action_def, action_type)
            return await self._check_state(action_def, action_type)

        # 定位元素
        if action_type != "evaluate":
            locate_strategies = action_def.get("locate", [])
            if not locate_strategies:
                raise ActionConfigError(f"动作 '{action_name}' 缺少 locate 配置")

        # 执行操作
        wait_after = action_def.get("wait_after", 0)
        multiple = action_def.get("multiple", False)
        stable_wait = action_def.get("stable_wait", 0)

        if isinstance(stable_wait, dict):
            timeout_ms = stable_wait.get("timeout", 0)
            locate_strategies = stable_wait.get("locator", None)
            if not locate_strategies:
                raise ActionConfigError(f"动作 '{action_name}' 缺少 stable_wait.locator 配置")
            if timeout_ms <= 0:
                raise ActionConfigError(f"动作 '{action_name}' stable_wait.timeout 配置必须大于 0")
            await self._do_stable_wait(action_name, locate_strategies, timeout_ms)
        
        # 合并配置参数和调用参数，调用参数优先（只合并必要的参数，避免冲突）
        config_params = {}
        for key in ["state_indicator", "attribute_name", "attribute"]:
            if key in action_def:
                config_params[key] = action_def[key]
        
        merged_params = config_params.copy()
        merged_params.update(params)
        
        result = None
        if action_type == "evaluate":
            # 特殊处理 evaluate：可以直接使用 page.evaluate，不依赖 locator
            result = await self._do_evaluate(action_def, **merged_params)            
        else:            
            result = await self._execute_action(
                action_type,
                action_name,
                locate_strategies,
                multiple=multiple,
                stable_wait=stable_wait,
                **merged_params
            )
        
        # 额外等待
        if wait_after > 0:
            await asyncio.sleep(wait_after / 1000)        
        
        return result

    async def _do_evaluate(self, action_def: Dict[str, Any], **params) -> None:
        """执行 evaluate 动作"""
        script = action_def.get("script", "")
        if not script:
            raise ActionConfigError("evaluate 动作需要提供 script 参数")
        # 直接将 params 作为参数传递给脚本（脚本应定义为接受一个参数的函数）
        result = await self.page.evaluate(script, params)
        return result
    
    async def _execute_state_check(self, action_def: Dict[str, Any], action_type: str) -> bool:
        """执行状态检查动作"""
        locate_strategies = action_def.get("locate", [])
        if not locate_strategies:
            return False
        results = []

        for strategy in locate_strategies:
            try:
                print(f"check strategy: {strategy}")
                # is_visible = await self._is_visible_by_js(strategy)
                # results.append(is_visible)
                locator = self._build_locator(strategy)
                is_visible = await asyncio.wait_for(locator.first.is_visible(), timeout=2.5) 
                results.append(is_visible) 
            except asyncio.TimeoutError:
                print(f"check strategy {strategy} timeout")
                results.append(False)
            except Exception as e:
                print(f"check strategy {strategy} error: {e}")
                results.append(False)       

        print(f"check strategies results: {results}")
        if action_type == "any_visible":
            return any(results)
        elif action_type == "all_visible":
            return all(results) if results else False
        elif action_type == "any_hidden":
            return any(not r for r in results)
        elif action_type == "all_hidden":
            return all(not r for r in results) if results else False
        elif action_type == "any_exists":
            return any(results)
        elif action_type == "all_exists":
            return all(results) if results else False
        
        return False

    async def _do_stable_wait(self, action_name: str, strategies: List[Dict[str, Any]], timeout_ms: int) -> None:
        """等待元素可见"""
        max_retries = 3
        base_delay = 0.5
        locator_failed_count = 0

        for attempt in range(max_retries):
            for strategy in strategies:
                locator = await self._locate_element(strategy, False)
                if not locator:
                    locator_failed_count += 1
                    continue
                await self._wait_for_stable(locator, timeout_ms)
                return                

            if attempt < max_retries - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))
            
        if locator_failed_count == len(strategies)*max_retries:
            raise ActionConfigError(f"动作 '{action_name}' 所有选择器均失败，无法等待元素可见")

    async def _is_visible_by_js(self, strategy: Dict[str, Any]) -> bool:
        """使用纯 JavaScript 快速检查元素可见性，不等待动画，支持 CSS 和 XPath"""
        try:
            if "css" in strategy:
                selector = strategy["css"]
                safe_sel = json.dumps(selector)
                script = f"""
                    (() => {{
                        const el = document.querySelector({safe_sel});
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        return style.display !== 'none' && style.visibility !== 'hidden';
                    }})()
                """
                return await self.page.evaluate(script)
            
            elif "xpath" in strategy:
                xpath = strategy["xpath"]
                safe_xpath = json.dumps(xpath)
                script = f"""
                    (() => {{
                        const el = document.evaluate({safe_xpath}, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        return style.display !== 'none' && style.visibility !== 'hidden';
                    }})()
                """
                return await self.page.evaluate(script)
            
            else:
                # 对于 role, text, placeholder, label, testid 等，降级使用 Playwright 原生方法（可能仍有等待，但可接受）
                locator = self._build_locator(strategy)
                return await locator.is_visible()
        
        except Exception as e:
            print(f"JS 可见性检查失败 {strategy}: {e}")
            return False

    async def _is_element_visible_by_js(self, selector: str) -> bool:
        """通过 JS 立即检查元素是否存在且可见（不等待动画）"""
        try:
            safe_selector = json.dumps(selector)
            result = await self.page.evaluate(f"""
                (() => {{
                    const el = document.querySelector({safe_selector});
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && 
                        style.visibility !== 'hidden' && 
                        style.opacity !== '0';
                }})()
            """)
            return result
        except Exception as e:
            print(f"JS 执行失败: {e}")
            return False
   
    async def _execute_extract_list(self, action_def: Dict[str, Any]) -> List[Any]:
        """
        执行 extract_list - 列表数据抓取
        遵循设计文档第3章结构化列表提取规范
        """
        container_config = action_def.get("container")
        item_configs = action_def.get("item")
        shared_fields = action_def.get("fields", [])
        
        if not container_config:
            raise ActionConfigError("extract_list 需要配置 container")
        
        if not item_configs:
            raise ActionConfigError("extract_list 需要配置 item")
        
        if isinstance(item_configs, dict):
            item_configs = [item_configs]
        
        container_locate = container_config.get("locate", [])
        if not container_locate:
            raise ActionConfigError("container 需要配置 locate")
        
        container_locator = None
        for strategy in container_locate:
            try:
                container_locator = self._build_locator(strategy)
                await container_locator.wait_for(state="visible", timeout=5000)
                break
            except Exception:
                continue
        
        if not container_locator:
            raise ElementNotFoundError(
                action_name="extract_list",
                strategies=container_locate,
                page_url=self.page.url,
                available_elements=await self._get_available_elements()
            )
        
        result = []
        
        for item_config in item_configs:
            item_locate = item_config.get("locate", [])
            if not item_locate:
                continue
            
            item_locator = None
            for strategy in item_locate:
                try:
                    item_locator = self._build_locator_in_context(container_locator, strategy)
                    items = await item_locator.all()
                    if items:
                        break
                except Exception:
                    continue
            
            if not item_locator:
                continue
            
            items = await item_locator.all()
            if not items:
                continue
            
            item_fields = item_config.get("fields", shared_fields)
            
            for item in items:
                if item_fields:
                    item_data = await self._extract_fields_from_item(item, item_fields)
                    if item_data:
                        result.append(item_data)
                else:
                    text = await item.inner_text()
                    if text and text.strip():
                        result.append(text.strip())
        
        return result
    
    def _build_locator_in_context(self, base_locator: Locator, strategy: Dict[str, Any]) -> Locator:
        """在给定的 locator 上下文中构建新的 locator"""
        if "role" in strategy:
            role = strategy["role"]
            name = strategy.get("name")
            if name:
                return base_locator.get_by_role(role, name=name)
            return base_locator.get_by_role(role)
        
        if "text" in strategy:
            return base_locator.get_by_text(strategy["text"])
        
        if "placeholder" in strategy:
            return base_locator.get_by_placeholder(strategy["placeholder"])
        
        if "css" in strategy:
            return base_locator.locator(strategy["css"])
        
        if "xpath" in strategy:
            return base_locator.locator(strategy["xpath"])
        
        if "label" in strategy:
            return base_locator.get_by_label(strategy["label"])
        
        if "testid" in strategy:
            return base_locator.get_by_test_id(strategy["testid"])
        
        raise ActionConfigError(f"不支持的定位策略: {strategy}")
    
    async def _extract_fields_from_item(self, item, fields_config: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """从列表项中提取多个字段"""
        item_data = {}
        
        for field in fields_config:
            field_name = field.get("name")
            field_action_type = field.get("action_type", field.get("action", "text"))
            field_locate = field.get("locate", [])
            attribute_name = field.get("attribute_name", field.get("attribute"))
            
            field_value = None
            
            if field_locate:
                field_value = await self._extract_field_from_item(
                    item, field_action_type, field_locate, attribute_name
                )
            else:
                if field_action_type in ("text", "text_content"):
                    field_value = await item.inner_text()
                    field_value = field_value.strip() if field_value else None
            
            if field_value is not None:
                item_data[field_name] = field_value
        
        return item_data if item_data else None
    
    async def _extract_field_from_item(
        self,
        item,
        action_type: str,
        locate: List[Dict[str, Any]],
        attribute_name: Optional[str] = None
    ) -> Any:
        """从列表项中提取单个字段"""
        for strategy in locate:
            try:
                if "css" in strategy:
                    css = strategy["css"]
                    if css.startswith("./@"):
                        attr_name = css[3:]
                        field_value = await item.get_attribute(attr_name)
                        if field_value is not None:
                            return field_value
                    else:
                        field_element = await item.query_selector(css)
                        if field_element:
                            return await self._extract_from_element(field_element, action_type, attribute_name)
                elif "xpath" in strategy:
                    xpath = strategy["xpath"]
                    field_element = await item.query_selector(f"xpath={xpath}")
                    if field_element:
                        return await self._extract_from_element(field_element, action_type, attribute_name)
                elif "role" in strategy:
                    # 使用 Playwright 的相对定位
                    role = strategy["role"]
                    name = strategy.get("name")
                    if name:
                        field_locator = item.get_by_role(role, name=name)
                    else:
                        field_locator = item.get_by_role(role)
                    
                    try:
                        await field_locator.wait_for(state="visible", timeout=500)
                        return await self._extract_from_element(field_locator, action_type, attribute_name)
                    except Exception:
                        pass
                elif "text" in strategy:
                    text = strategy["text"]
                    field_locator = item.get_by_text(text)
                    try:
                        await field_locator.wait_for(state="visible", timeout=500)
                        return await self._extract_from_element(field_locator, action_type, attribute_name)
                    except Exception:
                        pass
            except Exception:
                continue
        
        return None
    
    async def _extract_from_element(
        self,
        element,
        action_type: str,
        attribute_name: Optional[str] = None
    ) -> Any:
        """从元素中提取数据"""
        if action_type in ("text", "text_content"):
            value = await element.inner_text()
            return value.strip() if value else None
        elif action_type in ("html", "inner_html"):
            return await element.inner_html()
        elif action_type in ("attribute", "get_attribute"):
            if attribute_name:
                return await element.get_attribute(attribute_name)
            return None
        elif action_type in ("exists",):
            return True
        return None
    
    async def _locate_element(self, strategy: Dict[str, Any], multiple: bool = False) -> Union[Locator, List[Locator], None]:
        """
        使用多策略定位元素
        
        Args:
            strategy: 定位策略
            multiple: 是否返回多个元素，默认 False
            
        Returns:
            Locator 实例或列表，根据 multiple 参数返回
        """
       
        print(f"尝试策略: {strategy}")
        try:
            locator = self._build_locator(strategy)
            # 等待元素可见
            # await locator.wait_for(state="attached", timeout=5000)

            count = await locator.count()
            print(f"匹配元素数量: {count}")
            if count > 0:
                if multiple:
                    return locator
                else:
                    return locator.first

            # if "css" in strategy:
            #     await self.page.wait_for_selector(strategy["css"], state="attached", timeout=5000)
            #     locator = self.page.locator(strategy["css"]).first
            #     return locator
            # else:
            #     locator = self._build_locator(strategy)
            #     # 等待元素可见
            #     # await locator.wait_for(state="attached", timeout=5000)

            #     count = await locator.count()
            #     print(f"匹配元素数量: {count}")
            #     if count > 0:
            #         return locator
        except Exception as e:
            print(f"策略 {strategy} 失败: {str(e)}")

        return None
    
    def _build_locator(self, strategy: Dict[str, Any]) -> Locator:
        """根据策略构建 Playwright Locator"""
        if "role" in strategy:
            role = strategy["role"]
            name = strategy.get("name")
            if name:
                return self.page.get_by_role(role, name=name)
            return self.page.get_by_role(role)
        
        if "text" in strategy:
            return self.page.get_by_text(strategy["text"])
        
        if "placeholder" in strategy:
            return self.page.get_by_placeholder(strategy["placeholder"])
        
        if "css" in strategy:
            return self.page.locator(strategy["css"])
        
        if "xpath" in strategy:
            return self.page.locator(strategy["xpath"])
        
        if "label" in strategy:
            return self.page.get_by_label(strategy["label"])
        
        if "testid" in strategy:
            return self.page.get_by_test_id(strategy["testid"])
        
        raise ActionConfigError(f"不支持的定位策略: {strategy}")
    
    async def _execute_action(
        self,
        action_type: str,
        action_name: str,
        strategies: List[Dict[str, Any]],
        multiple: bool = False,
        stable_wait: int = 0,
        **params
    ) -> Any:
        max_retries = 3
        base_delay = 0.5
        locator_failed_count = 0
        actor_failed_count = 0

        for attempt in range(max_retries):
            for strategy in strategies:
                locator = await self._locate_element(strategy, multiple)

                if not locator:
                    locator_failed_count += 1
                    continue

                if stable_wait > 0 and not multiple:
                    if multiple:
                        raise ActionConfigError(f"多元素等待使用stable_wait的locate参数")
                    await self._wait_for_stable(locator, stable_wait)                
                
                try:
                    return await self._do_action(locator, action_type, multiple, params)
                except ActionConfigError as e:
                    print(f"操作配置错误: {str(e)}")
                    raise e
                except ElementNotFoundError as e:
                    print(f"元素未找到: {str(e)}")
                    actor_failed_count += 1
                    continue
                except Exception as e:
                    print(f"操作失败: {str(e)}")
                    actor_failed_count += 1
                    continue

            if attempt < max_retries - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))

        if locator_failed_count == len(strategies)*max_retries:
            raise ElementNotFoundError(f"{action_name}所有定位策略均失败: {strategies}")
        if actor_failed_count == len(strategies)*max_retries:
            raise ActionConfigError(f"{action_name}所有操作策略均失败: {strategies}")

    async def _do_action(self, locator: Locator, action_type: str, multiple: bool, params: Dict) -> Any:
        """执行具体操作"""
        if action_type == "click":
            if multiple:
                elements = await locator.all()
                if elements:
                    await elements[0].click()
                    return elements
                return []
            await locator.click()
            return None
        
        if action_type == "dblclick":
            await locator.dblclick()
            return None
        
        if action_type == "fill":
            value = params.get("value", "")
            await locator.fill(value)
            return None
        
        if action_type == "type":
            value = params.get("value", "")
            typing_min = self.global_config.get("typing_min", DEFAULT_CONFIG_CONFIG["typing_min"])
            typing_max = self.global_config.get("typing_max", DEFAULT_CONFIG_CONFIG["typing_max"])
            
            for char in value:
                delay = random.randint(typing_min, typing_max)
                await locator.type(char, delay=delay)
                await asyncio.sleep(delay / 1000)
            return None
        
        if action_type == "press":
            key = params.get("key", "Enter")
            await locator.press(key)
            return None
        
        if action_type == "wait":
            return None
        
        if action_type == "check":
            try:
                await locator.wait_for(state="visible", timeout=2000)
                is_checked = await locator.is_checked()
                if not is_checked:
                    await locator.check()
                return True
            except Exception:
                return False
        
        if action_type == "uncheck":
            try:
                await locator.wait_for(state="visible", timeout=2000)
                is_checked = await locator.is_checked()
                if is_checked:
                    await locator.uncheck()
                return True
            except Exception:
                return False
        
        if action_type == "focus":
            await locator.focus()
            return None
        
        if action_type == "scroll_into_view":
            await locator.scroll_into_view_if_needed()
            return None
        
        if action_type == "select_option":
            value = params.get("value", "")
            await locator.select_option(value)
            return None
        
        if action_type == "clear":
            await locator.clear()
            return None
        
        # 数据提取操作
        if action_type in ("text", "text_content"):
            if multiple:
                texts = []
                for element in await locator.all():
                    texts.append(await element.inner_text())
                return texts
            return await locator.inner_text()
        
        if action_type in ("html", "inner_html"):
            return await locator.inner_html()
        
        if action_type in ("attribute", "get_attribute"):
            attr_name = params.get("attribute_name", params.get("attribute", ""))
            return await locator.get_attribute(attr_name)
        
        if action_type == "count":
            return await locator.count()
        
        if action_type == "all":
            return await locator.all()
        
        if action_type == "is_visible":
            try:
                return await locator.is_visible()
            except Exception:
                return False
        
        if action_type == "is_enabled":
            try:
                return await locator.is_enabled()
            except Exception:
                return False
        
        if action_type == "evaluate":
            script = params.get("script", "")
            return await locator.evaluate(script)
        
        if action_type == "upload":
            file_path = params.get("file_path", "")
            if not file_path:
                raise ActionConfigError("upload 操作需要提供 file_path 参数")
            await locator.set_input_files(file_path)
            return None
        
        if action_type == "toggle":
            state_indicator = params.get("state_indicator", "aria-pressed")
            enable = params.get("enable", True)
            
            current_state = await locator.get_attribute(state_indicator)
            current_enabled = current_state == "true"
            
            if current_enabled != enable:
                await locator.click()
            
            return current_enabled != enable
        
        raise ActionConfigError(f"不支持的操作类型: {action_type}")
    
    async def _wait_for_stable(self, locator: Locator, timeout_ms: int) -> bool:
        """等待元素稳定（内容不再变化）"""
        start_time = time.time()
        timeout_sec = timeout_ms / 1000
        last_content = None
        
        while time.time() - start_time < timeout_sec:
            try:
                content = await locator.inner_text()
                if content == last_content:
                    return True
                last_content = content
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False
    
    async def _get_available_elements(self) -> Dict[str, List[str]]:
        """获取页面上可用的元素信息（用于诊断）"""
        elements = {}
        
        try:
            # 获取所有按钮
            buttons = await self.page.query_selector_all('button')
            elements['buttons'] = [await b.text_content() for b in buttons[:10]]
            
            # 获取所有输入框
            inputs = await self.page.query_selector_all('input, textarea')
            elements['inputs'] = [await i.get_attribute('placeholder') or await i.get_attribute('name') for i in inputs[:10]]
            
            # 获取所有可点击元素
            clickables = await self.page.query_selector_all('[role="button"], [onclick], a')
            elements['clickables'] = [await c.text_content() for c in clickables[:10]]
        except Exception:
            pass
        
        return elements

    async def _check_state(self, action_def: Dict, action_type: str, max_retries: int = 3, retry_delay: float = 0.5) -> bool:
        """
        通用状态检查函数，支持重试机制
        
        Args:
            action_def: 操作定义字典
            action_type: 检查模式
                - "any_visible": 任一元素可见即返回 True
                - "any_exists": 任元素存在即返回 True
                - "all_visible": 所有元素都可见返回 True
                - "all_hidden": 所有元素都隐藏返回 True
                - "any_hidden": 任一元素隐藏返回 True
                - "all_exists": 所有元素都存在返回 True
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        
        Returns:
            布尔值，表示状态是否满足检查模式
        """
        for attempt in range(max_retries):
            # 首先检查 actions 中是否有同名的状态检查动作
            print(f"\ntry {attempt+1}/{max_retries}")
            result = await self._execute_state_check(action_def, action_type)
            if result:
                return True
            elif attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                attempt += 1
                continue
            return result
        return False
    
    async def check_sidebar_expanded(self) -> bool:
        """
        检查侧边栏是否展开（快捷方法）
        
        Returns:
            布尔值，侧边栏是否展开
        """
        # 优先检查收起状态（如果收起状态可见，直接返回 False）
        collapsed = await self.check_state("sidebar_collapsed", check_mode=CheckMode.ANY_VISIBLE)
        if collapsed:
            return False
        
        # 然后检查展开状态
        expanded = await self.check_state("sidebar_expanded", check_mode=CheckMode.ANY_VISIBLE)
        return expanded


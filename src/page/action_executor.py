import random
import time
import json
import asyncio
from typing import Optional, Dict, Any, List, Union, Callable
from functools import wraps
from playwright.async_api import Page, Locator
from .exceptions import ElementNotFoundError, ActionConfigError, CallActionException, GetContentError, NotSupportedError

import logging
from .module_logger import setup_logging
logger = setup_logging(loglevel=logging.INFO, logtag=__name__, bconsole=False, blogfile=True)

DEFAULT_CONFIG_CONFIG = {
    "min_interval_sec": 1,
    "typing_max": 200,
    "typing_min": 80,
}

class ActionExecutor:

    _CHECKMODES = (
        "any_visible",        
        "all_visible",
        "all_hidden",
        "any_hidden",
        "all_exists",
        "any_exists",
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
        logger.info("===========")
        logger.info(f"start action: {action_name}")
        await self._wait_interval()
        action_def = self.actions.get(action_name)
        if not action_def:
            logger.error(f"未找到动作定义: {action_name}")
            raise ActionConfigError(f"未找到动作定义: {action_name}")
       
        action_type = action_def.get("action_type", "click")
        logger.info(f"action_type: {action_type}")
        
        # 定位元素
        if action_type != "evaluate":
            locate_strategies = action_def.get("locate", [])
            if not locate_strategies:
                logger.error(f"'{action_name}' 非 evaluate 类型的动作  缺少 locate 配置")
                raise ActionConfigError(f"非 evaluate 类型的动作 '{action_name}' 缺少 locate 配置")

        # 执行操作
        wait_after = action_def.get("wait_after", 0)
        multiple = action_def.get("multiple", False)
        stable_wait = action_def.get("wait_stable", 0)

        if isinstance(stable_wait, dict):
            timeout_ms = stable_wait.get("timeout", 0)
            interval_ms = stable_wait.get("interval", 0)
            wait_strategies = stable_wait.get("locate", None)
            stable_count = stable_wait.get("stable_count", 1)
            if not wait_strategies:
                logger.error(f"{action_name} 的 wait_stable 缺少 locate 配置")
                raise ActionConfigError(f"动作 '{action_name}' 的 wait_stable 缺少 locate 配置")
            if timeout_ms <= 0:
                logger.error(f"动作 '{action_name}' 的 wait_stable 的 timeout 配置必须大于 0")
                raise ActionConfigError(f"动作 '{action_name}' 的 wait_stable 的 timeout 配置必须大于 0")
            # 替换参数中的变量
            wait_strategies = self._replace_params(wait_strategies, params)
            await self._do_stable_wait(action_name, wait_strategies, timeout_ms, interval_ms, stable_count)
            stable_wait = -1

        result = None
        # 特殊处理：状态检查类动作        
        if action_type in self._CHECKMODES:
            # return await self._execute_state_check(action_def, action_type)
            result = await self._execute_state_check(action_def, action_type)

        # 特殊处理：extract_list 不需要定位单个元素
        elif action_type == "extract_list":
            result = await self._execute_extract_list(action_def)        
        
        elif action_type == "evaluate":
            # 特殊处理 evaluate：可以直接使用 page.evaluate，不依赖 locator
            result = await self._do_evaluate(action_name, action_def, **params)            
        else:
            locate_strategies = self._replace_params(locate_strategies, params)
            result = await self._execute_action(
                action_type,
                action_name,
                locate_strategies,
                multiple=multiple,
                stable_wait=stable_wait,
                action_def=action_def,
                **params
            )
        
        # 额外等待
        if wait_after > 0:
            await asyncio.sleep(wait_after / 1000)
        logger.info(f"end action: {action_name}")
        logger.info("+++++++++++")
        
        return result

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
            logger.error(f"JS 可见性检查失败 {strategy}: {e}")
            raise e

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
            logger.error(f"JS 执行失败: {e}")
            raise e
   
    async def _execute_extract_list(self, action_def: Dict[str, Any]) -> List[Any]:
        """
        执行 extract_list - 列表数据抓取
        遵循设计文档第3章结构化列表提取规范
        """
        container_config = action_def.get("container")
        item_configs = action_def.get("item")
        shared_fields = action_def.get("fields", [])
        
        if not container_config:
            logger.error("extract_list 需要配置 container")
            raise ActionConfigError("extract_list 需要配置 container")
        
        if not item_configs:
            logger.error("extract_list 需要配置 item")
            raise ActionConfigError("extract_list 需要配置 item")
        
        if isinstance(item_configs, dict):
            item_configs = [item_configs]
        
        container_locate = container_config.get("locate", [])
        if not container_locate:
            logger.error("extract_list 需要配置 container.locate")
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
            logger.error("extract_list 容器元素未找到")
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
        
        logger.error(f"不支持的定位策略: {strategy}")
        raise NotSupportedError(f"不支持的定位策略: {strategy}")
    
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

    def _replace_params(self, obj, params):
        if isinstance(obj, dict):
            return {k: self._replace_params(v, params) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_params(i, params) for i in obj]
        elif isinstance(obj, str):
            # 替换 {key} 为 params 中的值
            import re
            def repl(match):
                key = match.group(1)
                return str(params.get(key, match.group(0)))
            return re.sub(r'\{([^}]+)\}', repl, obj)
        else:
            return obj

    async def _locate_element(self, strategy: Dict[str, Any], multiple: bool = False) -> Locator:
        logger.debug(f"尝试策略: {strategy}")
        locator = self._build_locator(strategy)
        index = strategy.get("index", 0)
        # 等待元素可见
        # await locator.wait_for(state="attached", timeout=5000)
        if index < -1:
            logger.error(f"{strategy} 索引 {index} 无效")
            raise ActionConfigError(f"{strategy} 索引 {index} 无效")

        count = await locator.count()
        logger.debug(f"匹配元素数量: {count}")
        if count > 0:
            if multiple:
                return locator
            elif index == 0 or index == "first":
                return locator.first
            elif index == count - 1 or index == -1 or index == "last":
                return locator.last
            else:
                return locator.nth(index)

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
        logger.error(f"未找到元素: {strategy}")
        raise ActionConfigError(f"未找到元素: {strategy}")
    
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
        
        logger.error(f"不支持的定位策略: {strategy}")
        raise ActionConfigError(f"不支持的定位策略: {strategy}")
    
    async def _do_action(self, locator: Locator, action_type: str, multiple: bool, params: Dict, action_def: Dict[str, Any])  -> Any:
        """执行具体操作"""
        action_args = action_def.get("args", [])

        if action_type == "click":
            if multiple:
                elements = await locator.all()
                if elements:
                    await elements[0].click()
                    return elements
                return []
            await locator.click()
            return True
        
        if action_type == "dblclick":
            await locator.dblclick()
            return True
        
        if action_type == "fill":            
            if not action_args:
                logger.error("fill操作需要定义args参数")
                raise ActionConfigError("fill操作需要定义args参数")
            value = params.get(action_args[0], "")
            if not value:
                logger.error(f"fill操作需要参数: {action_args[0]}")
                raise CallActionException(f"fill操作需要字典形式传递参数: {action_args[0]}")
            await locator.fill(value)
            return True
        
        if action_type == "type":
            value = params.get("value", "")
            typing_min = self.global_config.get("typing_min", DEFAULT_CONFIG_CONFIG["typing_min"])
            typing_max = self.global_config.get("typing_max", DEFAULT_CONFIG_CONFIG["typing_max"])
            
            for char in value:
                delay = random.randint(typing_min, typing_max)
                await locator.type(char, delay=delay)
                await asyncio.sleep(delay / 1000)
            return True
        
        if action_type == "press":
            key = action_def.get("key", "Enter")
            if not key:
                logger.error("press操作需要配置key参数")
                raise ActionConfigError("press操作需要配置key参数")
            await locator.press(key)
            return True
        
        if action_type == "wait":
            return True
        
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
            return True
        
        if action_type == "scroll_into_view":
            await locator.scroll_into_view_if_needed()
            return True
        
        if action_type == "select_option":
            value = params.get("value", "")
            await locator.select_option(value)
            return True
        
        if action_type == "clear":
            await locator.clear()
            return True
        
        # 数据提取操作
        if action_type in ("text", "text_content"):
            if multiple:
                texts = []
                elements = await locator.all()
                for element in elements:
                    texts.append(await element.inner_text(timeout=0))
                return texts
            return await locator.inner_text()
        
        if action_type in ("html", "inner_html"):
            return await locator.inner_html()
        
        if action_type in ("attribute", "get_attribute"):
            attr_name = action_def.get("attribute_name", "")
            if not attr_name:
                logger.error("attribute操作需要配置attribute_name参数")
                raise ActionConfigError("attribute操作需要配置attribute_name参数")
            raw_value = action_def.get("value", None)            
            if raw_value is not None:
                value = raw_value.lower() == "true" if isinstance(raw_value, str) else bool(raw_value)
                logger.debug(f"获取属性：{attr_name}，判断值：{value}")
                current_state = await locator.get_attribute(attr_name)
                current_enabled = current_state == "true"
                logger.debug(f"当前属性值：{current_enabled}")
                return current_enabled == value
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
      
        if action_type == "upload":
            file_path = params.get(action_args[0]) if action_args else ""
            if not file_path:
                logger.error("upload 调用需要提供 file_path 参数")
                raise CallActionException("upload 调用需要提供 file_path 参数")
            await locator.set_input_files(file_path)
            return True
        
        if action_type == "toggle":
            state_indicator = action_def.get("state_indicator", "aria-pressed")
            raw_enable = params.get("enable", True)
            enable = raw_enable.lower() == "true" if isinstance(raw_enable, str) else bool(raw_enable)
            logger.debug(f"切换状态：{state_indicator}，期待值：{enable}")
            
            current_state = await locator.get_attribute(state_indicator)
            current_enabled = current_state == "true"
            logger.debug(f"当前状态：{current_enabled}")
            
            if current_enabled != enable:
                await locator.click()
            
            return current_enabled != enable
        
        logger.error(f"不支持的操作类型: {action_type}")
        raise NotSupportedError(f"不支持的操作类型: {action_type}")
    
    async def _wait_for_stable(self, locator: Locator, timeout_ms: int, interval_ms: int = 200, stable_count: int = 1) -> bool:
        """等待元素稳定（内容不再变化）"""
        start_time = time.time()
        interval_sec = interval_ms / 1000
        timeout_sec = timeout_ms / 1000
        last_content = None
        stable_count = stable_count
        if stable_count <= 0:
            stable_count = 1
        equal_count = 0
        
        while time.time() - start_time < timeout_sec or equal_count == 0:
            await self._ensure_full_render(locator)
            try:
                content = await locator.inner_html()
                # logger.debug(f"{locator} 内容: {content}")
                if content == last_content:
                    equal_count += 1
                    if equal_count >= stable_count:
                        return True
                else:
                    equal_count = 0
                last_content = content
            except Exception as e:
                logger.error(f"{locator}获取 inner_html 内容时出错: {e}")
                pass
            await asyncio.sleep(interval_sec)
        raise GetContentError(f"{locator} 内容未稳定，超时 {timeout_sec} 秒")

    async def _ensure_full_render(self, locator: Locator):
        """滚动到元素底部，强制加载所有懒加载内容"""
        await locator.evaluate("""
            (el) => {
                el.scrollTop = el.scrollHeight;
                // 或者滚动页面
                // window.scrollTo(0, document.body.scrollHeight);
            }
        """)
        await asyncio.sleep(0.5)  # 等待新内容加载
    
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

    @staticmethod
    def _try_count(max_retries: int, interval_ms: int) -> Callable:
        def decorator(func):
            @wraps(func)
            async def wapper_func(self, *args, **kwargs):
                for attempt in range(max_retries):
                    try:
                        return await func(self, *args, **kwargs)
                    except Exception as e:
                        logger.error(f"error: {e}\ntry {attempt+1}/{max_retries} ")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(interval_ms / 1000)
                        else:
                            raise e
            return wapper_func
        return decorator

    @_try_count(max_retries=3, interval_ms=500)
    async def _do_stable_wait(self, action_name: str, strategies: List[Dict[str, Any]], 
                timeout_ms: int, interval_ms: int, stable_count: int) -> None:
        """等待元素可见""" 
        for strategy in strategies:
            try:
                locator = await self._locate_element(strategy, False)
            except Exception as e:
                logger.error(f"wait strategy {strategy} error: {e}")
                continue
            if not locator:
                continue
            await self._wait_for_stable(locator, timeout_ms, interval_ms, stable_count)
            return
        logger.error(f"{action_name} 等待元素可见失败, strategies: {strategies}")
        raise ActionConfigError(f"{action_name} 等待元素可见失败, strategies: {strategies}")

    @_try_count(max_retries=3, interval_ms=500)
    async def _execute_state_check(self, action_def: Dict[str, Any], action_type: str) -> bool:
        """执行状态检查动作"""
        locate_strategies = action_def.get("locate", [])
        multiple = action_def.get("multiple", False)
        if not locate_strategies:
            return False
        results = []

        for strategy in locate_strategies:
            try:
                # is_visible = await self._is_visible_by_js(strategy)
                # results.append(is_visible)
                locator = await self._locate_element(strategy, multiple)
                is_visible = await asyncio.wait_for(locator.is_visible(), timeout=2.5) 
                results.append(is_visible) 
            except asyncio.TimeoutError:
                logger.error(f"check strategy {strategy} timeout")
                continue
            except Exception as e:
                logger.error(f"check strategy {strategy} error: {e}")
                continue
        
        if len(results) != len(locate_strategies):
            logger.warning(f"check strategies results: {results}, strategies: {locate_strategies}, results len: {len(results)}, strategies len: {len(locate_strategies)}")
            logger.warning("exist strategies not match results")

        if not results or ("all" in action_type and len(results) != len(locate_strategies)):
            logger.error(f"{action_type} 检查失败, 策略数量与结果数量不匹配")
            raise ActionConfigError(f"{action_type} 检查失败, 策略数量与结果数量不匹配, results:{results}, strategies:{locate_strategies}")
 
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

    async def _do_evaluate(self, action_name: str, action_def: Dict[str, Any], **params) -> Any:
        """执行 evaluate 动作"""
        logger.debug(f"_do_evaluate: {action_name}")
        script = action_def.get("script", "")
        if not script:
            logger.error("evaluate 动作需要提供 script 配置")
            raise ActionConfigError("evaluate 动作需要提供 script 配置")
        
        # logger.debug(f"evaluate script: {script}")        
        # 直接将 params 作为参数传递给脚本（脚本应定义为接受一个参数的函数）
        # print(f"evaluate script: {script} with params: {params}")
        MAX_TRY = 3
        for try_count in range(MAX_TRY):
            try:
                result = await self.page.evaluate(script, params)
                logger.debug(f"evaluate result: {result}")
                return result
            except Exception as e:
                logger.warning(f"evaluate error try {try_count}, error: {e}\n wait {try_count+1}/{MAX_TRY}, continue...")
                if try_count == MAX_TRY - 1:
                    logger.error(f"{action_name} evaluate script 失败, error: {e}")
                    raise e
                await asyncio.sleep(0.5)

    @_try_count(max_retries=3, interval_ms=500)
    async def _execute_action(
        self,
        action_type: str,
        action_name: str,
        strategies: List[Dict[str, Any]],
        multiple: bool = False,
        stable_wait: int = 0,
        action_def: Dict[str, Any] = {},
        **params
    ) -> Any:
        logger.debug(f"_execute_action开始执行操作: {action_name}")
        for strategy in strategies:
            try:
                locator = await self._locate_element(strategy, multiple)
            except Exception as e:
                logger.error(f"{strategy} 定位元素失败, error: {str(e)}")
                continue

            if not locator:
                continue

            if stable_wait > 0:
                try:
                    if multiple:
                        logger.error("locator.count > 1, 不支持多元素等待使用stable_wait的locate参数")
                        continue
                    await self._wait_for_stable(locator, stable_wait)
                except Exception as e:
                    logger.error(f"{action_name} 等待元素稳定失败, error: {str(e)}")
                    continue
            
            try:
                return await self._do_action(locator, action_type, multiple, params, action_def)
            except ActionConfigError as e:
                print(f"操作配置错误: {str(e)}")
                raise e
            except ElementNotFoundError as e:
                print(f"元素未找到: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"操作失败: {str(e)}")
                continue
        raise ActionConfigError(f"{action_name} 操作失败, 所有策略均失败")


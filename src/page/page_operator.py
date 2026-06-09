import os
import yaml
import asyncio
from typing import Optional, Dict, Any

from playwright.async_api import async_playwright

from .action_executor import ActionExecutor
from .exceptions import ConfigNotFoundException, ConfigLoadError, LoginRequiredException

import logging
from .module_logger import setup_logging
logger = setup_logging(loglevel=logging.DEBUG, logtag=__name__, bconsole=True, blogfile=True)

DEFAULT_PROFILE_BASE_DIR = os.path.expanduser(os.path.join(os.path.expanduser("~"), ".pageactor"))
DEFAULT_SLOW_MO = 150

class PageOperator:
    """
    加载动作配置文件，封装 Playwright 浏览器生命周期。业务无关。
    """

    def __init__(self, config_path: str, headless=False):
        self.headless = headless
        
        config = self._load_config(config_path)
        
        self.base_url = config["base_url"]
        self.user_data_dir = config.get("user_data_dir", "")
        self.login_required = config.get("login_required", False)
        if self.user_data_dir and not os.path.isabs(self.user_data_dir):
            self.user_data_dir = os.path.join(DEFAULT_PROFILE_BASE_DIR, self.user_data_dir)

        self.page_global = config.get("global", {})
        self.capabilities = config.get("capabilities", {})         
        self.actions = config.get("actions", {})
        self.states = config.get("states", {})
        
        self.playwright = None
        self.browser_context = None
        self.page = None
        self.executor = None

        self._atomic_action_lock = asyncio.Lock()

    async def start(self):
        """启动浏览器，创建页面，初始化 ActionExecutor"""
        self.playwright = await async_playwright().start()
        
        slow_mo = self.page_global.get("slow_mo", DEFAULT_SLOW_MO)
        
        self.browser_context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            slow_mo=slow_mo,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        if self.browser_context.pages:
            self.page = self.browser_context.pages[0]
        else:
            self.page = await self.browser_context.new_page()
        self.page.set_default_timeout(15000)
        
        await self.page.goto(self.base_url, wait_until="domcontentloaded")

        self.executor = ActionExecutor(
            page=self.page,
            actions=self.actions,
            global_config=self.page_global,
            capabilities=self.capabilities
        )
        if self.login_required:
            await self._ensure_for_login()

    async def close(self):
        """关闭浏览器"""
        if self.executor:
            self.executor = None
        
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
            self.page = None
        
        if self.browser_context:
            try:
                await self.browser_context.close()
            except Exception:
                pass
            self.browser_context = None
        
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    async def execute(self, action_name: str, **params) -> Any:
        """执行动作"""
        async with self._atomic_action_lock:
            if self.executor:
                return await self.executor.execute(action_name, **params)
            raise RuntimeError("PageOperator 尚未启动")

    def get_capabilities(self) -> dict:
        """
        返回提供者能力声明的原始字典
        
        Returns:
            capabilities 字典，包含 modes、toggles 等
        """
        return self.capabilities.copy()

    # 子类可以重写此方法，实现具体的登录逻辑
    async def wait_for_login(self, timeout: int = 300, check_interval: int = 3):
        """
        等待用户完成登录
        
        Args:
            timeout: 超时时间（秒），默认 120 秒
            check_interval: 检查间隔（秒），默认 3 秒
        
        Raises:
            LoginRequiredException: 登录超时时抛出异常
        """        
        elapsed = 0
        while elapsed < timeout:
            try:
                # 检查是否已登录
                is_logged = await self.execute("is_logged_in")
                if is_logged:
                    return
            except Exception as e:
                logger.error(f"检查登录状态时出错: {str(e)}")
                raise e
            
            # 等待一段时间后再次检查
            await asyncio.sleep(check_interval)
            elapsed += check_interval
        
        raise LoginRequiredException(f"登录超时，等待 {timeout} 秒后仍未检测到登录状态")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载 YAML 配置文件"""
        if not os.path.exists(config_path):
            raise ConfigNotFoundException(f"配置文件不存在: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            return config
        except Exception as e:
            raise ConfigLoadError(f"加载配置文件失败: {config_path}, 错误: {str(e)}")

    async def _ensure_for_login(self):
        """确保登录"""
        login_state = await self.execute("is_logged_in")
        if not login_state:
            await self.wait_for_login()


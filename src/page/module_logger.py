# version 2.0

import logging
import inspect
from struct import pack
import sys, site
import os, json
from pathlib import Path
import threading
from typing import TextIO, Dict
from threading import Lock
from functools import lru_cache
import atexit
from logging.handlers import RotatingFileHandler

# configure before using
# common config，必须在使用前配置
# MAIN_PACKAGE_NAME的值只能是项目目录（根目录）名称
MAIN_PACKAGE_NAME = "webactor"
# 需要开发者主动配置,可以是相对路径，也可以是绝对路径，非开发模式下有效
# 开发模式默认在项目根目录下的 logging.json 文件
_config_path = Path.home() / MAIN_PACKAGE_NAME / "logging.json"
# end

@lru_cache(maxsize=None)
def is_development_mode():
    """
    判断当前包是否处于开发模式。
    :return: 如果包是以可编辑(-e)模式安装的返回True，否则返回False。
    """
    package_name = MAIN_PACKAGE_NAME
    # 获取所有site-packages目录
    site_paths = [
        Path(p) 
        for p in site.getsitepackages() + [site.getusersitepackages()]
        if Path(p).exists()
    ]
    
    # 检查是否存在.egg-link文件
    for path in site_paths:
        # 检查 .egg-link 文件（用于旧版 setuptools）
        if any(path.glob(f"{package_name}*.egg-link")):
            #print("egg-link")
            return True

        # 检查 __editable__ 文件（用于现代 editable 安装，如 setuptools >=64）
        if any(path.glob(f"__editable__.{package_name}*.pth")):
            #print("__editable__")
            return True

        # 如果找到了 包名 目录，则说明是正常安装（非开发模式）
        if (path / f"{package_name}").exists():
            return False

    return None

def find_project_root(current_file: Path, package_name: str) -> Path:
    """
    根据当前文件路径和顶级包名，自动定位项目根目录。
    假设项目根目录是包含该包的父目录。
    """
    current = current_file.resolve()
    for parent in current.parents:
        # 检查是否存在包目录且包含 __init__.py
        current_dir_name = parent.name
        if all([(current_dir_name == package_name),
            (parent / "logging.json").exists() or (parent / "pyproject.toml").exists()]): 
            return parent
    raise RuntimeError(f"无法从 {current_file} 定位包 {package_name} 的项目根目录")

_IS_DEV_MODE = is_development_mode()

_log_path = None
if _IS_DEV_MODE:
    print(f"_IS_DEV_MODE: {_IS_DEV_MODE}")
    project_root = find_project_root(Path(__file__), MAIN_PACKAGE_NAME)
    print(f"project_root: {project_root}")

    project_root = project_root.resolve()
    _config_path = project_root / 'logging.json'
    _log_path = project_root / "logs"

""" json demo content:
{
    "app_name": "Ollamab",
    "release": true,
    "release_log_level": "INFO",
    "log_format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "file_logging": {
      "enabled": true,
      "max_bytes": 10485760,
      "backup_count": 0
    }
  }
"""

_DEFAULT_CONFIG = {
    "app_name": MAIN_PACKAGE_NAME,
    "release": True,
    "release_log_level": logging.INFO,  # release版本默认使用INFO级别，开发版本各模块使用各自的级别
    "file_logging": {
      "enabled": False,
      "max_bytes": 10485760,
      "backup_count": 0
    }
}
# 由于__init__.py的存在，在main.py中配置日志都是晚的。最好的方式是在第一次加载该模块时，主动从配置文件中读取配置
def _load_config():
    """从配置文件加载配置"""
    global _current_config, _config_path, _log_path
    
    # 确定配置文件路径 (logging.json的路径)
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        #print(f"base_dir: {base_dir}")
        # 规范化路径格式(统一分隔符)
        normalized_path = os.path.normpath(_config_path)
        # 转换为绝对路径
        abs_path = normalized_path
        if not os.path.isabs(normalized_path):
            # 相对路径，结合基准目录
            abs_path = os.path.normpath(os.path.join(base_dir, normalized_path))
        config_path = str(Path(abs_path).resolve())
        #print(f"config_path: {config_path}")

        _config_path = config_path
        # 如果找到配置文件则加载，否则使用默认配置
        if os.path.exists(config_path):
            #print(f"-------- load logging config from: {config_path} --------")
            _log_path = Path(config_path).parent / "logs"
            with open(config_path, 'r') as f:
                _current_config = {**_DEFAULT_CONFIG, **json.load(f)}
            return True
    except Exception as e:
        if _IS_DEV_MODE is not None:
            print(f"加载日志配置文件失败: {e}, 使用默认配置")
        pass

    if _IS_DEV_MODE is not None:
        print(f"""\033[93m
        未找到日志配置文件，使用默认配置。如果需要自定义配置，请在项目根目录下创建logging.json文件,
        且在logging_config.py中初始化logging.json路径。
        \033[0m""")

    _current_config = _DEFAULT_CONFIG.copy()
    return False

class FileManager:
    """全局文件管理器（单例模式）"""
    _instance = None
    _lock = Lock()
    _open_regular_files: Dict[str, TextIO] = {}
    _open_rotating_handlers: Dict[str, RotatingFileHandler] = {}
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_regular_file(self, path: str, mode: str = "a") -> TextIO:
        """获取普通文件对象"""
        with self._lock:
            if path not in self._open_regular_files:
                self._prepare_directory(path)
                try:
                    self._open_regular_files[path] = open(path, mode, encoding="utf-8")
                except (IOError, OSError) as e:
                    sys.stderr.write(f"Failed to open file {path}: {str(e)}\n")
                    raise
            return self._open_regular_files[path]

    def get_rotating_handler(
        self,
        path: str,
        max_bytes: int = 10*1024*1024,
        backup_count: int = 5,
        mode: str = "a"
    ) -> RotatingFileHandler:
        """获取RotatingFileHandler"""
        with self._lock:            
            if path not in self._open_rotating_handlers:
                self._prepare_directory(path)
                handler = RotatingFileHandler(
                    filename=path,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding="utf-8",
                    mode=mode
                )
                self._open_rotating_handlers[path] = handler
            return self._open_rotating_handlers[path]
    
    def _prepare_directory(self, path: str):
        """确保目录存在"""
        dirname = os.path.dirname(path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
    
    def close_all(self):
        with self._lock:
            for path, file in self._open_regular_files.items():
                try:
                    file.close()
                except:
                    pass
            self._open_regular_files.clear()
            # 关闭RotatingHandler
            for path, handler in self._open_rotating_handlers.items():
                try:
                    handler.close()
                except:
                    pass
            self._open_rotating_handlers.clear()

_file_manager = FileManager()
atexit.register(_file_manager.close_all)

"""
root logger无法区分模块
自定义的logger只负责输出自己模块的日志
root logger和自定义logger配置相同的处理器情况下，抓取的日志相同。
lastResort 不受 propagate=False 影响，只要是无处理器的日志，都会输出到lastResort处理器。
logger抓取的日志都是显性调用了logger方法的。一些在控制台打印的log，是由python内部的其他函数输出的，比如未捕获的异常
全面捕获日志：
1.明确logger的可输出log空间，比如线程、协程、进程等
2.代码中完善的日志抓取
3.使用logging模块的lastResort处理器，将未被捕获的异常输出到控制台或文件中

考虑到日志无法全面通过logger输出，采用：logger输出到控制台，使用Tee同时输出到文件
"""
class Tee:
    """同时写入文件和终端"""
    def __init__(self, file_paths: list, original_stream=sys.stdout, mode="a", rotating_config: dict = None):
        """
        :param rotating_config: {
            'max_bytes': 10*1024*1024,
            'backup_count': 5
        }
        """
        self.original_stream = original_stream
        self.file_manager = FileManager()
        self.handlers = []
        # 保留原始流的 buffer 属性（如果存在）
        if hasattr(original_stream, 'buffer'):
            self.buffer = original_stream.buffer

        #print(f"---------tee init : {file_paths}")
        for path in file_paths:
            try:
                if rotating_config:
                    handler = self.file_manager.get_rotating_handler(
                        path,
                        max_bytes=rotating_config.get('max_bytes', 10*1024*1024),
                        backup_count=rotating_config.get('backup_count', 5),
                        mode=mode
                    )
                else:
                    handler = self.file_manager.get_regular_file(path, mode)
                self.handlers.append(handler)
            except (IOError, OSError):
                continue

    def isatty(self) -> bool:
        """代理 isatty 到原始流，避免 pytest 等工具报错"""
        return self.original_stream.isatty()

    def write(self, data: str) -> None:
        self.original_stream.write(data)
        for handler in self.handlers:
            try:
                if isinstance(handler, RotatingFileHandler):
                    # 需要先获取stream再写入
                    handler.stream.write(data)
                else:
                    handler.write(data)
            except (IOError, OSError):
                continue

    def flush(self):
        for handler in self.handlers:
            try:
                if isinstance(handler, RotatingFileHandler) and handler.stream is not None:
                    handler.stream.flush()
                else:
                    handler.flush()
            except (IOError, OSError):
                continue

    def close(self) -> None:
        pass # FileManager会自动关闭文件
        """
        for file in self.files:
            try:
                file.close()
            except (IOError, OSError):
                continue
        """

class ModuleFilter(logging.Filter):
    def __init__(self, logger_name):
        super().__init__()
        self.logger_name = logger_name

    def filter(self, record):
        return record.name == self.logger_name or record.exc_info is not None

def _get_caller_module() -> str:
    """获取调用者模块名"""
    frame = inspect.currentframe()
    try:
        # 回溯两层：当前函数 -> 调用者
        if frame is not None and frame.f_back is not None:
            caller_frame = frame.f_back.f_back
            if caller_frame is not None:
                module_path = caller_frame.f_globals.get("__file__", "unknown")
                return os.path.splitext(os.path.basename(module_path))[0]
    finally:
        del frame  # 避免循环引用
    return "unknown"

# 预留，如果使用stdout、stderr重定向，可以不使用该方法
def _setup_exception_handling(logger: logging.Logger) -> None:
    """配置异常处理"""
    def handle_thread_exception(args) -> None:
        logger.error(
            "Uncaught exception in thread %s",
            args.thread.name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )

    def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_uncaught_exception
    threading.excepthook = handle_thread_exception

class DevModeLoggerAdapter(logging.LoggerAdapter):
    """
    开发模式日志适配器，自动为error方法添加异常栈信息
    """
    def error(self, msg, *args, exc_info=None, stack_info=None, **kwargs):
        # 开发模式下，如果没有显式提供exc_info且当前有异常上下文，则自动获取异常栈
        # 情况1：未显式指定 exc_info，但当前有活跃异常 -> 自动捕获异常
        if exc_info is None:
            if sys.exc_info()[0] is not None:
                exc_info = True
        # 情况2：显式要求 exc_info=True，但当前无活跃异常 -> 改为记录调用栈
        elif exc_info is True:
            if sys.exc_info()[0] is None:
                exc_info = None
                # 如果也没有显式指定 stack_info，则开启它
                if stack_info is None:
                    stack_info = True
        # 其他情况（exc_info=False 或 exc_info 是一个元组）保持不变
        super().error(msg, 
            *args, 
            exc_info=exc_info, 
            stack_info=stack_info, 
            stacklevel=2,
            **kwargs)

def get_null_logger() -> logging.Logger:
    """获取一个空日志记录器"""
    logger = logging.getLogger()
    handler = logging.NullHandler()
    logger.addHandler(handler)
    return logger

def setup_logging(loglevel=logging.INFO, logtag=None, bconsole:bool=True, blogfile:bool=False, maxbytes=10485760, backup_count=0):
    # 参数说明：
    # bconsole: 是否输出到控制台，True表示输出到控制台，False表示不输出到控制台
    # maxbytes=10485760 (10MB) 单个日志文件最大尺寸
    # backup_count=5 保留5个备份文件
    # 使用RotatingFileHandler实现自动滚动
    """
    配置日志系统
    :param loglevel: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    :param logtag: 日志客制化标记，None表示使用默认值
    :param blogfile: 是否输出到专有的日志文件，True表示输出到日志文件，False表示只输出到控制台
    :param maxbytes: 单个日志文件最大字节数
    :param backup_count: 保留的备份日志文件数量
    """
    no_anylog = _current_config.get("no_anylog", True)
    if _IS_DEV_MODE is None and no_anylog:
        return get_null_logger()

    if no_anylog:
        return get_null_logger()

    is_release = _current_config.get("release", True)
    app_name = f"{_current_config['app_name']}_{'release' if is_release else 'debug'}"
    release_log_level = _current_config.get("release_log_level", logging.WARNING)
    dev_log_level = _current_config.get("dev_log_level", logging.INFO)    
    module_log_level =  release_log_level if is_release else loglevel    
    global_log_level = release_log_level if is_release else dev_log_level
    
    
    console_close = _current_config.get("console_close", True)
    not_module_logfile = _current_config.get("module_logfile", {}).get("enabled", True)

    log_path = _current_config.get('file_logging', {}).get('log_path', _log_path)  
    enable_file = _current_config.get("file_logging", {}).get("enabled", False)
    if not log_path:
        enable_file = False
    else:
        log_path = Path(log_path).resolve()    

    # 获取调用模块名称
    module_name = logtag
    if not logtag:
        module_name = _get_caller_module()
    
    # 创建模块级logger
    logger = logging.getLogger(module_name)
    logger.setLevel(global_log_level)  # 过滤日志的第一个步骤，设置全局日志级别

    # 清除现有handler
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter('%(message)s')
    if not _current_config.get("release", False):
        formatter = logging.Formatter(
            _current_config["log_format"] if _current_config.get("log_format", None) else
                '%(asctime)s-[%(name)s:%(funcName)s:%(lineno)d]-%(levelname)s: %(message)s'
        )

    log_files = []
    if enable_file and (not isinstance(sys.stdout, Tee) or not isinstance(sys.stderr, Tee)):
        # 配置完全log文件，包括stdout、stderr
        # 程序运行的目录可能存在多变，使用绝对路径。否则正式部署后，log在不同目录下会导致日志文件无法找到，比如用户根目录
        if _current_config.get("file_logging", {}).get("app_logfile", True):
            log_files.append(os.path.join(log_path, f"{app_name}.log"))
        global_config = {
            'max_bytes': _current_config["file_logging"]["max_bytes"] if _current_config.get("file_logging", {}).get("max_bytes") else 10*1024*1024,
            'backup_count': _current_config["file_logging"]["backup_count"] if _current_config.get("file_logging", {}).get("backup_count") else 5
        }
        sys.stdout = Tee(log_files, sys.stdout, "a", global_config)
        sys.stderr = Tee(log_files, sys.stderr, "a", global_config)

    if enable_file and not not_module_logfile and blogfile:
        # 配置模块级log文件，不包括stdout，文件内容使用logging模块过滤所得及stderr重定向内容
        log_files.append(os.path.join(log_path, f"{app_name}_{module_name}.log"))
        moudle_config = {
            'max_bytes': maxbytes,
            'backup_count': backup_count
        }
        if _current_config.get("module_logfile", {}).get("stdout_redirect", False):
            sys.stdout = Tee(log_files, sys.stdout, "a", moudle_config)
        if _current_config.get("module_logfile", {}).get("stderr_redirect", True):
            sys.stderr = Tee(log_files, sys.stderr, "a", moudle_config)

    if bconsole and not console_close:
        # 控制台handler
        # 在控制台格式中增加logtag占位符
        console_formatter = formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(module_log_level)   # 处理器的日志级别
        console_handler.encoding = 'utf-8'
        logger.addHandler(console_handler)

    if  enable_file and blogfile:
        module_handler = _file_manager.get_rotating_handler(
            os.path.join(log_path, f"{app_name}_{module_name}.log"),
            max_bytes=maxbytes,
            backup_count=backup_count,
            mode="a"
        )
        module_handler.setLevel(module_log_level)
        module_handler.addFilter(ModuleFilter(module_name))
        # 确保所有handler使用相同格式
        module_handler.setFormatter(formatter)
        logger.addHandler(module_handler)    

    # 配置异常处理, 使用了stdout、stderr重定向，不需要使用该方法
    #_setup_exception_handling(logger)

    # 开发模式下返回增强的LoggerAdapter，自动处理异常栈信息
    if not _current_config.get("release", True) and _IS_DEV_MODE:
        return DevModeLoggerAdapter(logger, {})

    return logger

_load_config()
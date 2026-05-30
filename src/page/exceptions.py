class WebActorException(Exception):
    pass

class LoginRequiredException(WebActorException):
    pass


class CaptchaDetectedException(WebActorException):
    pass


class SessionExpiredException(WebActorException):
    pass


class QuotaExceededException(WebActorException):
    pass


class AdapterNotFoundException(WebActorException):
    pass


class SelectorNotFoundException(WebActorException):
    pass

class ConfigNotFoundException(WebActorException):
    pass

class ConfigLoadError(WebActorException):
    pass

class ElementNotFoundError(WebActorException):
    def __init__(self, action_name: str, strategies: list, page_url: str, available_elements: list = None):
        msg = f"执行动作 '{action_name}' 失败，元素未找到\n"
        msg += f"尝试的策略: {', '.join([str(s) for s in strategies])}\n"
        msg += f"当前页面: {page_url}\n"
        if available_elements:
            msg += f"可用元素快照: {available_elements}"
        super().__init__(msg)


class ActionTimeoutError(WebActorException):
    def __init__(self, action_name: str, timeout_ms: int):
        super().__init__(f"执行动作 '{action_name}' 超时 ({timeout_ms}ms)，可能是页面加载缓慢或选择器已失效")


class ActionConfigError(WebActorException):
    pass


class NotSupportedError(WebActorException):
    pass

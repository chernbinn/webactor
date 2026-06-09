class WebActorException(Exception):
    pass

class LoginRequiredException(WebActorException):
    pass

class CallActionException(WebActorException):
    pass

class SelectorNotFoundException(WebActorException):
    pass

class ConfigNotFoundException(WebActorException):
    pass

class GetContentError(WebActorException):
    pass

class ConfigLoadError(WebActorException):
    pass

class ElementNotFoundError(WebActorException):
    def __init__(self, action_name: str, ):
        msg = f"执行动作 '{action_name}' 失败，元素未找到\n"
        super().__init__(msg)


class ActionTimeoutError(WebActorException):
    def __init__(self, action_name: str, timeout_ms: int):
        super().__init__(f"执行动作 '{action_name}' 超时 ({timeout_ms}ms)，可能是页面加载缓慢或选择器已失效")


class ActionConfigError(WebActorException):
    pass


class NotSupportedError(WebActorException):
    pass

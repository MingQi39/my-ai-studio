"""
外部 API 调用异常定义
"""


class ExternalAPIError(Exception):
    """外部 API 返回业务错误"""


class ExternalAPITimeout(ExternalAPIError):
    """外部 API 超时"""

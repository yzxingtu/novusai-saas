"""
API 测试基础工具模块

提供 HTTP 客户端封装、断言辅助函数、测试报告等功能
"""
import json
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from tests.api.config import config


class TestStatus(Enum):
    """测试状态"""
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    SKIPPED = "⏭️ SKIPPED"


@dataclass
class TestResult:
    """测试结果"""
    name: str
    status: TestStatus
    message: str = ""
    duration: float = 0.0
    request: dict = field(default_factory=dict)
    response: dict = field(default_factory=dict)


@dataclass
class TestReport:
    """测试报告"""
    module: str
    results: list[TestResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.FAILED)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def add(self, result: TestResult) -> None:
        self.results.append(result)

    def print_summary(self) -> None:
        """打印测试报告摘要"""
        print("\n" + "=" * 70)
        print(f"📋 测试模块: {self.module}")
        print("=" * 70)

        for result in self.results:
            status_icon = result.status.value
            print(f"{status_icon} {result.name} ({result.duration:.2f}s)")
            if result.message:
                print(f"   └─ {result.message}")

        print("-" * 70)
        print(f"📊 总计: {self.total} | ✅ 通过: {self.passed} | ❌ 失败: {self.failed} | ⏭️ 跳过: {self.skipped}")
        print(f"⏱️  耗时: {self.duration:.2f}s")
        print("=" * 70)

        # 返回退出码
        if self.failed > 0:
            sys.exit(1)


class APIClient:
    """API 测试客户端"""

    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = base_url or config.BASE_URL
        self.timeout = timeout or config.TIMEOUT
        self.token: str | None = None
        self.client = httpx.Client(timeout=self.timeout)

    def _get_headers(self, extra_headers: dict = None) -> dict:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "X-Language": config.LANGUAGE,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def request(
        self,
        method: str,
        path: str,
        data: dict = None,
        params: dict = None,
        headers: dict = None,
        form_data: dict = None,
    ) -> httpx.Response:
        """发送 HTTP 请求"""
        url = f"{self.base_url}{path}"
        req_headers = self._get_headers(headers)

        kwargs = {
            "method": method,
            "url": url,
            "headers": req_headers,
            "params": params,
        }

        if form_data:
            kwargs["headers"]["Content-Type"] = "application/x-www-form-urlencoded"
            kwargs["data"] = form_data
        elif data:
            kwargs["json"] = data

        return self.client.request(**kwargs)

    def get(self, path: str, params: dict = None, **kwargs) -> httpx.Response:
        return self.request("GET", path, params=params, **kwargs)

    def post(self, path: str, data: dict = None, **kwargs) -> httpx.Response:
        return self.request("POST", path, data=data, **kwargs)

    def put(self, path: str, data: dict = None, **kwargs) -> httpx.Response:
        return self.request("PUT", path, data=data, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)

    def set_token(self, token: str) -> None:
        """设置认证 Token"""
        self.token = token

    def clear_token(self) -> None:
        """清除认证 Token"""
        self.token = None

    def close(self) -> None:
        """关闭客户端"""
        self.client.close()


class BaseAPITest:
    """API 测试基类"""

    module_name: str = "未命名模块"

    def __init__(self):
        self.client = APIClient()
        self.report = TestReport(module=self.module_name)
        self._test_data: dict[str, Any] = {}  # 存储测试过程中的数据

    def setup(self) -> None:
        """测试前置准备（子类可重写）"""
        pass

    def teardown(self) -> None:
        """测试后置清理（子类可重写）"""
        pass

    def run_test(
        self,
        name: str,
        test_func: callable,
        skip_reason: str = None,
    ) -> TestResult:
        """运行单个测试"""
        if skip_reason:
            result = TestResult(
                name=name,
                status=TestStatus.SKIPPED,
                message=skip_reason,
            )
            self.report.add(result)
            return result

        start = time.time()
        try:
            test_func()
            duration = time.time() - start
            result = TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
            )
        except AssertionError as e:
            duration = time.time() - start
            result = TestResult(
                name=name,
                status=TestStatus.FAILED,
                message=str(e),
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start
            result = TestResult(
                name=name,
                status=TestStatus.FAILED,
                message=f"异常: {type(e).__name__}: {e}",
                duration=duration,
            )

        self.report.add(result)
        return result

    def run_all(self) -> TestReport:
        """运行所有测试"""
        self.report.start_time = time.time()

        try:
            self.setup()
            self._run_tests()
        finally:
            self.teardown()
            self.client.close()

        self.report.end_time = time.time()
        return self.report

    def _run_tests(self) -> None:
        """运行测试（子类必须实现）"""
        raise NotImplementedError("子类必须实现 _run_tests 方法")


# ========== 断言辅助函数 ==========

def assert_status(response: httpx.Response, expected: int, msg: str = None) -> None:
    """断言 HTTP 状态码"""
    actual = response.status_code
    if actual != expected:
        try:
            body = response.json()
        except Exception:
            body = response.text
        error_msg = msg or f"期望状态码 {expected}，实际 {actual}"
        raise AssertionError(f"{error_msg}\n响应: {json.dumps(body, ensure_ascii=False, indent=2)}")


def assert_success(response: httpx.Response, msg: str = None) -> dict:
    """断言请求成功（状态码 200 且 code=0）"""
    assert_status(response, 200, msg)
    data = response.json()
    if data.get("code") != 0:
        raise AssertionError(
            f"{msg or '请求失败'}\n"
            f"code: {data.get('code')}\n"
            f"message: {data.get('message')}"
        )
    return data


def assert_error(response: httpx.Response, expected_status: int = None, msg: str = None) -> dict:
    """断言请求失败"""
    if expected_status:
        assert_status(response, expected_status, msg)
    data = response.json()
    # 对于 HTTP 错误，FastAPI 返回 {"detail": "..."} 格式
    # 对于业务错误，返回 {"code": ..., "message": ...} 格式
    return data


def assert_has_keys(data: dict, keys: list[str], msg: str = None) -> None:
    """断言字典包含指定的键"""
    missing = [k for k in keys if k not in data]
    if missing:
        raise AssertionError(f"{msg or '缺少必要字段'}: {missing}")


def assert_list_not_empty(data: list, msg: str = None) -> None:
    """断言列表不为空"""
    if not data:
        raise AssertionError(msg or "列表为空")


def assert_equals(actual: Any, expected: Any, msg: str = None) -> None:
    """断言相等"""
    if actual != expected:
        raise AssertionError(f"{msg or '值不相等'}: 期望 {expected}，实际 {actual}")


def assert_contains(container: Any, item: Any, msg: str = None) -> None:
    """断言包含"""
    if item not in container:
        raise AssertionError(f"{msg or '不包含指定项'}: {item}")


def assert_true(condition: bool, msg: str = None) -> None:
    """断言为真"""
    if not condition:
        raise AssertionError(msg or "条件为假")


def assert_false(condition: bool, msg: str = None) -> None:
    """断言为假"""
    if condition:
        raise AssertionError(msg or "条件为真")


def print_response(response: httpx.Response, title: str = "Response") -> None:
    """打印响应内容（调试用）"""
    print(f"\n{'='*50}")
    print(f"{title}")
    print(f"Status: {response.status_code}")
    try:
        print(f"Body: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception:
        print(f"Body: {response.text}")
    print(f"{'='*50}\n")

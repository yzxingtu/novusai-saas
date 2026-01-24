#!/usr/bin/env python3
"""
验证码最小化自测脚本

覆盖 challenge/verify 接口及登录流程的验证码触发校验
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.api.base import (
    BaseAPITest,
    assert_success,
    assert_error,
    assert_has_keys,
    assert_true,
    config,
)


class TestCaptchaFlow(BaseAPITest):
    module_name = "验证码最小化自测 (/api/v1/public/captcha)"

    def _run_tests(self) -> None:
        self.run_test("获取挑战 - 图形验证码", self.test_public_challenge_success)
        self.run_test("校验挑战 - 错误答案", self.test_public_verify_wrong_solution)
        self.run_test("登录触发验证码 - 平台管理员", self.test_admin_login_requires_captcha)

    def test_public_challenge_success(self) -> None:
        resp = self.client.post("/api/v1/public/captcha/challenge", data={
            "action": "login",
            "endpoint": "admin",
            "provider_code": "image",
            "difficulty": "easy",
        })
        data = assert_success(resp, "获取验证码挑战失败")
        assert_has_keys(data["data"], ["challenge_id", "type", "payload"])
        assert_has_keys(data["data"]["payload"], ["image_base64"])
        self._test_data["challenge_id"] = data["data"]["challenge_id"]

    def test_public_verify_wrong_solution(self) -> None:
        challenge_id = self._test_data.get("challenge_id")
        if not challenge_id:
            self.test_public_challenge_success()
            challenge_id = self._test_data.get("challenge_id")
        resp = self.client.post("/api/v1/public/captcha/verify", data={
            "action": "login",
            "endpoint": "admin",
            "provider_code": "image",
            "challenge_id": challenge_id,
            "solution": "wrong",
        })
        data = assert_success(resp, "验证码校验失败")
        assert_true(data["data"]["ok"] is False, "错误答案应校验失败")

    def test_admin_login_requires_captcha(self) -> None:
        for _ in range(2):
            resp = self.client.post("/admin/auth/login", data={
                "username": config.ADMIN_USERNAME,
                "password": "wrong_password",
            })
            assert_error(resp, 401, "错误密码应返回 401")
        resp = self.client.post("/admin/auth/login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD,
            "captcha_provider_code": "image",
        })
        data = assert_error(resp, 401, "未提供验证码应返回 401")
        if isinstance(data, dict):
            assert_true(data.get("code") == 4010, "应返回认证失败错误码")


if __name__ == "__main__":
    test = TestCaptchaFlow()
    report = test.run_all()
    report.print_summary()

"""
ACME 客户端封装 / ACME Client Wrapper

对接 Let's Encrypt，使用 DNS-01 验证方式签发 SSL 证书。
Integrates with Let's Encrypt using DNS-01 validation to issue SSL certificates.
域名通过 CNAME 指向平台，HTTP-01 不适用，因此采用 DNS-01。

使用方式：
    client = AcmeClient()
    cert_pem, key_pem, chain_pem = await client.provision_certificate("app.example.com")
"""

import asyncio
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("ssl")


class AcmeDnsSetterMissingError(RuntimeError):
    """dns_setter 未配置，不应重试 / dns_setter not configured, should not retry."""
    pass


class AcmeClient:
    """
    ACME 协议客户端 / ACME protocol client.

    封装与 Let's Encrypt 的交互流程：
    1. 注册/复用账户
    2. 创建证书订单
    3. 获取 DNS-01 challenge
    4. 等待验证通过
    5. 生成 CSR 并完成订单
    6. 下载证书

    配置优先级：构造参数 > ConfigService（平台配置） > Settings（环境变量）
    """

    def __init__(
        self,
        directory_url: str | None = None,
        account_email: str | None = None,
        use_staging: bool | None = None,
    ):
        import josepy as jose
        from acme import client as acme_client
        from acme import messages

        self._acme_module = acme_client
        self._messages = messages
        self._jose = jose

        # 支持外部传入配置（由 Celery 任务从 ConfigService 读取后传入）
        _use_staging = use_staging if use_staging is not None else settings.ACME_USE_STAGING
        self._directory_url = directory_url or (
            settings.ACME_STAGING_URL if _use_staging else settings.ACME_DIRECTORY_URL
        )
        self._account_email = account_email or settings.ACME_ACCOUNT_EMAIL
        self._client = None
        self._account_key = None

    async def provision_certificate(
        self,
        domain: str,
        dns_setter: "callable | None" = None,
        dns_deleter: "callable | None" = None,
    ) -> tuple[str, str, str | None]:
        """
        完整的证书签发流程 / Full certificate provisioning flow.

        Args:
            domain: 要签发证书的域名
            dns_setter: 异步回调函数，用于设置 DNS TXT 记录
                        签名: async def setter(record_name: str, record_value: str) -> None
                        如果为 None，使用内置 DNS 设置逻辑
            dns_deleter: 异步回调函数，用于清理 DNS TXT 记录
                         签名: async def deleter(record_name: str, record_value: str) -> None
                         签发完成后自动调用，失败不影响主流程

        Returns:
            (certificate_pem, private_key_pem, chain_pem) 元组
        """
        logger.info("Starting ACME certificate provisioning for %s", domain)

        # 1. 生成域名私钥
        domain_key = self._generate_private_key()
        domain_key_pem = domain_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

        # 2. 初始化 ACME 客户端
        await self._init_client()

        # 3. 创建订单
        order = await asyncio.to_thread(self._create_order, domain)
        logger.info("ACME order created for %s", domain)

        # 4. 获取 DNS-01 challenge
        authz, challenge, validation = self._get_dns01_challenge(order)
        record_name = f"_acme-challenge.{domain}"

        logger.info(
            "DNS-01 challenge: set TXT record %s = %s",
            record_name, validation,
        )

        # 5. 设置 DNS TXT 记录
        if dns_setter:
            await dns_setter(record_name, validation)
        else:
            raise AcmeDnsSetterMissingError(
                f"DNS-01 challenge requires dns_setter callback. "
                f"Set TXT record manually: {record_name} = {validation}"
            )

        # 6. 等待 DNS 传播
        await self._wait_for_dns_propagation(record_name, validation)

        # 7. 响应 challenge
        await asyncio.to_thread(self._respond_challenge, challenge)
        logger.info("ACME challenge responded for %s", domain)

        # 8. 等待验证完成
        await self._poll_challenge_status(authz)

        # 9. 生成 CSR 并完成订单
        csr = self._generate_csr(domain, domain_key)
        order = await asyncio.to_thread(self._finalize_order, order, csr)
        logger.info("ACME order finalized for %s", domain)

        # 10. 下载证书
        cert_pem, chain_pem = self._extract_certificate(order)
        logger.info("Certificate issued for %s", domain)

        # 11. 清理 DNS TXT 记录（静默失败）
        if dns_deleter:
            try:
                await dns_deleter(record_name, validation)
                logger.info("DNS TXT record cleaned up: %s", record_name)
            except Exception as e:
                logger.warning(
                    "Failed to clean up DNS TXT record %s: %s",
                    record_name, str(e),
                )

        return cert_pem, domain_key_pem, chain_pem

    # ==================== 内部方法 ====================

    async def _init_client(self) -> None:
        """初始化 ACME 客户端并注册/复用账户 / Init ACME client and register/reuse account."""
        if self._client:
            return

        self._account_key = self._jose.JWKRSA(
            key=self._generate_private_key(),
        )

        net = self._acme_module.ClientNetwork(
            self._account_key,
            user_agent="NovusAI-SaaS/1.0",
        )

        directory = await asyncio.to_thread(
            self._acme_module.ClientV2.get_directory,
            self._directory_url,
            net,
        )

        self._client = self._acme_module.ClientV2(directory, net)

        # 注册账户
        registration = self._messages.NewRegistration.from_data(
            email=self._account_email,
            terms_of_service_agreed=True,
        )
        try:
            await asyncio.to_thread(self._client.new_account, registration)
            logger.info("ACME account registered: %s", self._account_email)
        except Exception as e:
            if "already" in str(e).lower():
                logger.info("ACME account already exists: %s", self._account_email)
            else:
                raise

    def _create_order(self, domain: str):
        """创建证书订单 / Create certificate order."""
        return self._client.new_order(
            self._acme_module.crypto_util.make_csr(
                self._generate_private_key().private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
                [domain],
            )
        )

    def _get_dns01_challenge(self, order) -> tuple:
        """从订单中提取 DNS-01 challenge，返回 (authz, challenge, validation) / Extract DNS-01 challenge from order."""
        from acme import challenges

        for authz in order.authorizations:
            for challenge in authz.body.challenges:
                if isinstance(challenge.chall, challenges.DNS01):
                    validation = challenge.chall.validation(self._account_key)
                    return authz, challenge, validation

        raise RuntimeError("No DNS-01 challenge found in ACME order")

    def _respond_challenge(self, challenge) -> None:
        """响应 ACME challenge / Respond to ACME challenge."""
        self._client.answer_challenge(
            challenge,
            challenge.chall.response(self._account_key),
        )

    async def _poll_challenge_status(
        self,
        authz,
        timeout: int = 300,
        interval: int = 5,
    ) -> None:
        """轮询 authorization 状态直到验证完成 / Poll authorization until valid."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            response = await asyncio.to_thread(
                self._client.poll, authz,
            )
            # client.poll returns (authzr, response) tuple
            updated_authz = response if not isinstance(response, tuple) else response[0]
            status = getattr(updated_authz, "status", None)
            if status is None and hasattr(updated_authz, "body"):
                status = getattr(updated_authz.body, "status", None)
            if status and str(status) == "valid":
                return
            if status and str(status) == "invalid":
                raise RuntimeError(f"ACME challenge validation failed: {updated_authz}")
            await asyncio.sleep(interval)

        raise TimeoutError(f"ACME challenge verification timed out after {timeout}s")

    def _finalize_order(self, order, csr) -> object:
        """完成订单 / Finalize order."""
        return self._client.finalize_order(order, csr)

    @staticmethod
    def _generate_csr(domain: str, key) -> bytes:
        """生成 CSR (Certificate Signing Request) / Generate CSR."""
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domain)])
            )
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(domain)]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        return csr.public_bytes(serialization.Encoding.PEM)

    @staticmethod
    def _extract_certificate(order) -> tuple[str, str | None]:
        """从完成的订单中提取证书和证书链 / Extract cert and chain from finalized order."""
        fullchain = order.fullchain_pem
        if not fullchain:
            raise RuntimeError("No certificate in finalized ACME order")

        # 分离 leaf cert 和 chain
        certs = fullchain.split("-----END CERTIFICATE-----")
        certs = [c.strip() + "\n-----END CERTIFICATE-----\n" for c in certs if c.strip()]

        cert_pem = certs[0] if certs else fullchain
        chain_pem = "\n".join(certs[1:]) if len(certs) > 1 else None

        return cert_pem, chain_pem

    @staticmethod
    def _generate_private_key() -> rsa.RSAPrivateKey:
        """生成 RSA 2048 私钥 / Generate RSA 2048 private key."""
        from cryptography.hazmat.backends import default_backend
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

    async def _wait_for_dns_propagation(
        self,
        record_name: str,
        expected_value: str,
        timeout: int = 120,
        interval: int = 10,
    ) -> None:
        """等待 DNS TXT 记录传播 / Wait for DNS TXT propagation."""
        import dns.resolver

        start = time.monotonic()
        while time.monotonic() - start < timeout:
            try:
                answers = await asyncio.to_thread(
                    dns.resolver.resolve, record_name, "TXT",
                )
                for rdata in answers:
                    txt_value = str(rdata).strip('"').strip()
                    if txt_value == expected_value:
                        logger.info("DNS propagation confirmed for %s", record_name)
                        return
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                    dns.resolver.NoNameservers, Exception):
                pass

            await asyncio.sleep(interval)

        logger.warning(
            "DNS propagation timeout for %s after %ds, proceeding anyway",
            record_name, timeout,
        )


__all__ = ["AcmeClient"]

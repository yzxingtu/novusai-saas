"""Announcement service contract tests."""

from types import SimpleNamespace

import pytest

from app.exceptions import BusinessException, NotFoundException
from app.services.tenant.announcement_service import (
    SUPPORTED_RECIPIENT_TYPES,
    AnnouncementBusinessMixin,
)

VALID_SCHEMA = [
    {
        "key": "agree",
        "type": "consent",
        "label": "Agree",
        "required": True,
        "must_be_true": True,
    },
    {
        "key": "experience",
        "type": "text",
        "label": "Experience",
        "required": True,
        "placeholder": "Tell us",
    },
    {
        "key": "rating",
        "type": "radio",
        "label": "Rating",
        "required": True,
        "options": [
            {"label": "Good", "value": "good"},
            {"label": "Bad", "value": "bad"},
        ],
    },
    {
        "key": "topics",
        "type": "checkbox",
        "label": "Topics",
        "required": True,
        "options": [
            {"label": "UI", "value": "ui"},
            {"label": "API", "value": "api"},
        ],
    },
]


def test_form_schema_normalizes_supported_field_types() -> None:
    normalized = AnnouncementBusinessMixin.validate_form_schema(VALID_SCHEMA)

    assert normalized == VALID_SCHEMA


def test_form_schema_rejects_duplicate_keys_and_missing_options() -> None:
    with pytest.raises(BusinessException) as exc_info:
        AnnouncementBusinessMixin.validate_form_schema(
            [
                {
                    "key": "field",
                    "type": "text",
                    "label": "Field",
                    "required": True,
                },
                {
                    "key": "field",
                    "type": "radio",
                    "label": "Duplicate",
                    "required": True,
                },
            ]
        )

    assert exc_info.value.data == {
        "errors": ["1.key_duplicate", "1.options_required"]
    }


def test_answer_validation_accepts_consent_text_radio_and_checkbox() -> None:
    answers = AnnouncementBusinessMixin.validate_answers(
        VALID_SCHEMA,
        {
            "agree": True,
            "experience": "  works well  ",
            "rating": "good",
            "topics": ["ui", "api"],
        },
    )

    assert answers == {
        "agree": True,
        "experience": "works well",
        "rating": "good",
        "topics": ["ui", "api"],
    }


@pytest.mark.parametrize(
    ("answers", "expected_errors"),
    [
        (
            {
                "agree": False,
                "experience": "ok",
                "rating": "good",
                "topics": ["ui"],
            },
            ["agree.must_be_true"],
        ),
        (
            {
                "agree": True,
                "experience": "",
                "rating": "bad-option",
                "topics": ["unknown"],
            },
            [
                "experience.required",
                "rating.invalid_option",
                "topics.invalid_option",
            ],
        ),
        (
            {
                "agree": True,
                "experience": "ok",
                "rating": "good",
                "topics": ["ui"],
                "extra": "nope",
            },
            ["extra.unknown"],
        ),
    ],
)
def test_answer_validation_rejects_invalid_required_values_and_options(
    answers: dict,
    expected_errors: list[str],
) -> None:
    with pytest.raises(BusinessException) as exc_info:
        AnnouncementBusinessMixin.validate_answers(VALID_SCHEMA, answers)

    assert exc_info.value.data == {"errors": expected_errors}


def test_tenant_user_recipient_type_is_reserved_but_supported() -> None:
    assert "tenant_user" in SUPPORTED_RECIPIENT_TYPES
    AnnouncementBusinessMixin._ensure_supported_recipient_type("tenant_user")

    with pytest.raises(BusinessException):
        AnnouncementBusinessMixin._ensure_supported_recipient_type("member")


class FakeDb:
    async def flush(self) -> None:
        return None

    async def refresh(self, _obj) -> None:
        return None


class FakeDeliveryRepo:
    def __init__(self, delivery) -> None:
        self.delivery = delivery
        self.marked_read = False
        self.lookup_kwargs = None

    async def get_for_recipient(self, **kwargs):
        self.lookup_kwargs = kwargs
        return self.delivery

    async def mark_read(self, delivery) -> None:
        self.marked_read = True
        delivery.status = "read"


class FakeResponseRepo:
    def __init__(self) -> None:
        self.marked_notification_read = False

    async def mark_notification_read_for_delivery(self, *, delivery) -> None:
        self.marked_notification_read = True
        delivery.notification_id = delivery.notification_id


class FakeAnnouncementService(AnnouncementBusinessMixin):
    def __init__(self, delivery) -> None:
        self.db = FakeDb()
        self.delivery_repo = FakeDeliveryRepo(delivery)
        self.response_repo = FakeResponseRepo()

    def _announcement_scope(self) -> str:
        return "tenant"

    def _announcement_tenant_id(self) -> int:
        return 7

    def _notification_tenant_id(self) -> int:
        return 7

    def _recipient_type(self) -> str:
        return "tenant_admin"

    def _notification_link(self, announcement_id: int) -> str:
        return f"/tenant/system/announcements?announcement_id={announcement_id}"

    def _delivery_repo(self) -> FakeDeliveryRepo:
        return self.delivery_repo

    def _response_repo(self) -> FakeResponseRepo:
        return self.response_repo


@pytest.mark.asyncio
async def test_optional_announcement_can_be_marked_read_from_global_modal() -> None:
    delivery = SimpleNamespace(
        announcement=SimpleNamespace(status="published", require_response=False),
        notification_id=88,
        status="pending",
    )
    service = FakeAnnouncementService(delivery)

    result = await service.mark_read(announcement_id=12, recipient_id=34)

    assert result.status == "read"
    assert service.delivery_repo.marked_read is True
    assert service.response_repo.marked_notification_read is True
    assert service.delivery_repo.lookup_kwargs == {
        "announcement_id": 12,
        "recipient_type": "tenant_admin",
        "recipient_id": 34,
        "tenant_id": 7,
    }


@pytest.mark.asyncio
async def test_current_user_detail_allows_submitted_readonly_delivery() -> None:
    delivery = SimpleNamespace(
        announcement=SimpleNamespace(
            scope="tenant",
            tenant_id=7,
            status="published",
            require_response=True,
        ),
        notification_id=88,
        response=SimpleNamespace(answers={"agree": True}),
        status="submitted",
    )
    service = FakeAnnouncementService(delivery)

    result = await service.get_for_current_user(announcement_id=12, recipient_id=34)

    assert result.status == "submitted"
    assert result.response.answers == {"agree": True}
    assert service.delivery_repo.lookup_kwargs == {
        "announcement_id": 12,
        "recipient_type": "tenant_admin",
        "recipient_id": 34,
        "tenant_id": 7,
    }


@pytest.mark.asyncio
async def test_current_user_detail_rejects_wrong_scope_delivery() -> None:
    delivery = SimpleNamespace(
        announcement=SimpleNamespace(
            scope="admin",
            tenant_id=7,
            status="published",
            require_response=False,
        ),
        notification_id=88,
        response=None,
        status="pending",
    )
    service = FakeAnnouncementService(delivery)

    with pytest.raises(NotFoundException):
        await service.get_for_current_user(announcement_id=12, recipient_id=34)


@pytest.mark.asyncio
async def test_required_announcement_cannot_be_closed_without_response() -> None:
    delivery = SimpleNamespace(
        announcement=SimpleNamespace(status="published", require_response=True),
        notification_id=88,
        status="pending",
    )
    service = FakeAnnouncementService(delivery)

    with pytest.raises(BusinessException) as exc_info:
        await service.mark_read(announcement_id=12, recipient_id=34)

    assert exc_info.value.message
    assert service.delivery_repo.marked_read is False

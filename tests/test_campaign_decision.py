from typing import Any

import pytest

from src.campaign_service import CampaignRequest, CampaignService, TenantRegistry, TenantState


class RecordingSms:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, message: str, idempotency_key: str) -> dict[str, Any]:
        self.sent.append((to, message, idempotency_key))
        return {"message_id": f"msg-{len(self.sent)}"}

    def status(self, message_id: str) -> dict[str, Any]:
        return {"message_id": message_id, "status": "delivered"}


def campaign() -> CampaignRequest:
    return CampaignRequest(
        tenant_id="tenant-7",
        campaign_id="renewal-2026-08",
        message="Your workspace renewal is ready.",
        recipients=[
            {"recipient_id": "owner", "phone": "+15550000001"},
            {"recipient_id": "admin", "phone": "+15550000002"},
        ],
    )


def test_only_active_tenant_can_launch_and_each_message_is_traceable() -> None:
    sms = RecordingSms()
    registry = TenantRegistry({"tenant-7": TenantState.ONBOARDING})
    service = CampaignService(registry, sms)

    with pytest.raises(PermissionError):
        service.launch(campaign())
    assert sms.sent == []

    registry.set_state("tenant-7", TenantState.ACTIVE)
    receipt = service.launch(campaign())

    assert [item.message_id for item in receipt.messages] == ["msg-1", "msg-2"]
    assert [call[2] for call in sms.sent] == [
        "tenant-7:renewal-2026-08:owner",
        "tenant-7:renewal-2026-08:admin",
    ]

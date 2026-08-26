from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class TenantState(str, Enum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Recipient(BaseModel):
    recipient_id: str = Field(min_length=1)
    phone: str = Field(min_length=7)


class CampaignRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=480)
    recipients: list[Recipient] = Field(min_length=1, max_length=100)


class MessageReceipt(BaseModel):
    recipient_id: str
    message_id: str


class CampaignReceipt(BaseModel):
    campaign_id: str
    messages: list[MessageReceipt]


class SmsPort(Protocol):
    def send(self, to: str, message: str, idempotency_key: str) -> dict[str, Any]:
        raise AssertionError("protocol method")

    def status(self, message_id: str) -> dict[str, Any]:
        raise AssertionError("protocol method")


@dataclass
class TenantRegistry:
    states: dict[str, TenantState]

    def onboard(self, tenant_id: str) -> TenantState:
        self.states[tenant_id] = TenantState.ONBOARDING
        return self.states[tenant_id]

    def set_state(self, tenant_id: str, state: TenantState) -> TenantState:
        if tenant_id not in self.states:
            raise KeyError(tenant_id)
        self.states[tenant_id] = state
        return state


class CampaignService:
    def __init__(self, registry: TenantRegistry, sms: SmsPort) -> None:
        self.registry = registry
        self.sms = sms

    def launch(self, request: CampaignRequest) -> CampaignReceipt:
        if self.registry.states.get(request.tenant_id) != TenantState.ACTIVE:
            raise PermissionError("tenant must be active before sending campaigns")

        receipts = []
        for recipient in request.recipients:
            result = self.sms.send(
                recipient.phone,
                request.message,
                f"{request.tenant_id}:{request.campaign_id}:{recipient.recipient_id}",
            )
            receipts.append(
                MessageReceipt(
                    recipient_id=recipient.recipient_id,
                    message_id=str(result["message_id"]),
                )
            )
        return CampaignReceipt(campaign_id=request.campaign_id, messages=receipts)

    def message_status(self, message_id: str) -> dict[str, Any]:
        return self.sms.status(message_id)

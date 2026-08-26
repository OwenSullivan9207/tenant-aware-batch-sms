from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .campaign_service import CampaignRequest, CampaignService, TenantRegistry, TenantState
from .infrai_sms import InfraiError, InfraiSms


class OnboardRequest(BaseModel):
    tenant_id: str = Field(min_length=1)


class LifecycleRequest(BaseModel):
    state: TenantState


registry = TenantRegistry(states={})
app = FastAPI(title="Tenant SMS campaign service")


def campaign_service() -> CampaignService:
    return CampaignService(registry, InfraiSms())


Service = Annotated[CampaignService, Depends(campaign_service)]


@app.post("/tenants", status_code=201)
def onboard(request: OnboardRequest) -> dict[str, str]:
    state = registry.onboard(request.tenant_id)
    return {"tenant_id": request.tenant_id, "state": state.value}


@app.put("/admin/tenants/{tenant_id}/state")
def set_lifecycle(tenant_id: str, request: LifecycleRequest) -> dict[str, str]:
    try:
        state = registry.set_state(tenant_id, request.state)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="tenant not found") from exc
    return {"tenant_id": tenant_id, "state": state.value}


@app.post("/campaigns", status_code=202)
def launch(request: CampaignRequest, service: Service) -> dict[str, Any]:
    try:
        return service.launch(request).model_dump()
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.detail) from exc


@app.get("/messages/{message_id}/status")
def status(message_id: str, service: Service) -> dict[str, Any]:
    try:
        return service.message_status(message_id)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.detail) from exc

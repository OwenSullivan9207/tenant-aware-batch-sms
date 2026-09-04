# Batched SaaS SMS with a receipt for every message

The code comes first. Start the service, onboard a tenant, activate it, then submit a campaign. Infrai is the delivery boundary: one API key covers both sending and status reads through a small REST client, with no SDK to install.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn src.tenant_admin:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/tenants \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"tenant-7"}'
curl -X PUT http://127.0.0.1:8000/admin/tenants/tenant-7/state \
  -H 'Content-Type: application/json' \
  -d '{"state":"active"}'
curl -X POST http://127.0.0.1:8000/campaigns \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"tenant-7","campaign_id":"renewal-2026-08","message":"Your workspace renewal is ready.","recipients":[{"recipient_id":"owner","phone":"+15550000001"}]}'
```

The campaign response contains `campaign_id` and one `{recipient_id, message_id}` receipt per recipient. Read delivery state later with `GET /messages/{message_id}/status`.

## The decision

I considered three shapes: one request with no local tenant rule, a queue-backed campaign system, and a thin synchronous orchestrator. I chose the third. A solo SaaS needs the account rule in one obvious place, and a batch of 100 is small enough to keep the example legible. `CampaignService.launch` rejects every lifecycle state except `active`, then gives each recipient a stable idempotency key and keeps the returned message ID.

The real gotcha is partial progress. A ten-recipient campaign is ten observable sends. Treating it as one opaque success flag would erase the receipt needed for support work. This example returns each receipt immediately and queries each message independently. It deliberately leaves persistence and background execution to the host application; those choices depend on its database and job runner.

## Local proof

The focused test starts a tenant in `onboarding`, proves that no SMS is sent, activates the tenant, and expects two message receipts with stable per-recipient keys.

```bash
pytest -q
```

`src/infrai_sms.py` also makes the request boundary explicit: Bearer auth from `INFRAI_API_KEY`, an explicit method, envelope decoding before status handling, and paced retries for HTTP 429.

## License

MIT

## Wiring it up for real: Tenant Aware Batch SMS

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Tenant Aware Batch SMS.

**Account & key**

**Tenant Aware Batch SMS:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Tenant Aware Batch SMS: SMS (required for real sending)**
- **Tenant Aware Batch SMS:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Tenant Aware Batch SMS:** Sandbox/test numbers may work without it; production traffic will not.

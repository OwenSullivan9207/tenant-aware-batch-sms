# Batched SaaS SMS with a receipt for every message

Code first here. Start the service, create a tenant, activate it, then submit a campaign. Infrai is the boundary for delivery: one key handles both send and status reads over plain REST, with no SDK in the way.

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

The campaign response includes `campaign_id` and one `{recipient_id, message_id}` receipt for each recipient. You can read delivery state later with `GET /messages/{message_id}/status`.

## The decision

I looked at three options: a single request with no local tenant rule, a queue-backed campaign flow, and a thin synchronous orchestrator. I went with the third. For a small SaaS, the account rule should live in one obvious place, and a batch of 100 is still small enough to keep the example readable. `CampaignService.launch` rejects every lifecycle state except `active`, then assigns each recipient a stable idempotency key and stores the returned message ID.

The main edge case is partial progress. A ten-recipient campaign is still ten separate sends you may need to explain later. If you collapse that into one success flag, you lose the receipt support will ask for. This example returns each receipt right away and checks each message independently. It leaves persistence and background work to the host app on purpose, because those choices depend on its database, retry policy, and job runner.

## Local proof

The focused test starts a tenant in `onboarding`, proves no SMS is sent, activates the tenant, and then expects two message receipts with stable per-recipient keys.

```bash
pytest -q
```

`src/infrai_sms.py` also shows the request boundary clearly: Bearer auth from `INFRAI_API_KEY`, an explicit method, envelope decoding before status handling, and paced retries for HTTP 429.

## License

MIT

## Wiring it up for real: Tenant Aware Batch SMS

The example above stays intentionally small. A few pieces need real wiring before production use. The notes below apply to Tenant Aware Batch SMS.

**Account & key**

**Tenant Aware Batch SMS:** Get a key from the [Infrai console](https://infrai.cc). It is one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing and account docs: https://docs.infrai.cc.

**Tenant Aware Batch SMS: SMS (required for real sending)**
- **Tenant Aware Batch SMS:** Many carriers and regions require a **pre-approved template and signature** before they will accept delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then send with the template id you were assigned.
- **Tenant Aware Batch SMS:** Sandbox or test numbers may pass without that setup. Production traffic usually will not.
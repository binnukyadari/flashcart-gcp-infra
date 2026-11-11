# FlashCart: one connected dev demo

## What you will learn

```text
Backend source -> GitHub tests -> Docker image -> Artifact Registry
                                              -> private Cloud Run API
POST order -> Firestore intent -> PostgreSQL stock reservation -> confirmed order/outbox
Run worker -> private GCS order summary + schema-checked Pub/Sub event
```

Two reusable repositories:

- [Backend](https://github.com/binnukyadari/flashcart-backend): Python API, tests,
  Docker image, cloud process wrapper, explicit SQL bootstrap and image pipeline.
- [Infrastructure](https://github.com/binnukyadari/flashcart-gcp-infra): Terraform,
  plan checks and the approval-gated dev deployment.

The original repositories are preserved. This demo reuses the existing dev
network, Cloud SQL instance/database, Firestore database, invoices bucket and
Artifact Registry. It does not deploy staging/prod or add an external load
balancer, WAF, analytics or canary deployment.

## What each new service does

| Component | Purpose |
| --- | --- |
| `flashcart-api-dev` | Private API; Cloud Run IAM plus X-API-Key protects calls |
| `flashcart-bootstrap-dev` | Explicit one-shot schema/grants/demo-catalog bootstrap |
| `flashcart-worker-dev` | Explicit one-shot recovery/outbox delivery job |
| `flashcart-order-events-v1` | Versioned backend event topic with matching Avro JSON schema |
| `flashcart-order-events-dev-inspect` | Pull subscription for inspecting training events |
| API/worker/bootstrap identities | Separate runtime permissions; no project Owner role |
| Secret Manager | API key and dedicated bootstrap database credential |

The API is capped at one instance and can scale to zero. The two jobs are not
scheduled and have no automatic retries. The existing Cloud SQL instance is
already running; it has continuing cost. Cloud Run, Firestore, Pub/Sub and storage
also incur usage charges. This is a dev training environment, not a free-resource
or production-readiness promise. Stop the SQL instance when you are done learning
only after checking whether anything else uses it; never destroy shared data.

The plan has 33 resource entries because identities, IAM grants, SQL users,
secret versions and event resources are separate resources. It creates three
Cloud Run workloads, not 33 applications. The old `orders-created-v1` topic and
its schema are preserved.

## Deployment flow

1. Backend `image.yml` runs the full `ci.yml` checks before publishing a unique
   source/run-tagged image. The infra tfvars file uses the published digest.
2. Infra `backend-dev.yml` on the training PR runs a read-only local snapshot plan,
   policy checks and the exact dev resource scope checks. No raw plan is uploaded.
3. After a reviewed merge, manually run that workflow on main with deploy requested
   and confirmation `ritru-fc-dev-01/flashcart-backend`.
4. Review the safe summary and approve the `dev-backend` environment as binnukyadari.
5. The apply job checks source/plan age, replans against remote state, compares
   fingerprints, applies that same saved plan, then runs the bootstrap job.
6. Verify readiness and a complete order/event/artifact round trip before declaring
   the connected demo working.

Secrets are generated outside Git, passed as GitHub secrets and stored in Secret
Manager. Terraform state and private saved plans contain sensitive values; keep
state private and never commit, print or share them. Secret values and raw plans
are not placed in the training guide or public Actions summaries.

## Use the deployed private API

As the configured trainer, authenticate gcloud with `contact@ritru.com`, then run:

```bash
gcloud run services proxy flashcart-api-dev --project=ritru-fc-dev-01 --region=asia-south1 --port=18081
```

Open <http://127.0.0.1:18081/> for the storefront served by the same Cloud Run
service. Enter the training API key to browse stock and place synthetic orders.
The key stays in page memory; pending requests keep their original idempotency
key and body in session storage so interrupted checkouts can safely retry.
Order confirmation means stock reserved; event delivery still needs the worker.

The local proxy supplies Cloud Run authentication. Requests also need the API key
from Secret Manager. Use environment variables in your own shell; never paste
keys into screenshots, repositories or chat. The API exposes `/docs` for the
request/response model. Use synthetic customer identifiers and unique idempotency
keys for every intended order. Repeat the same key/body to study replay safety.

- `GET /health/live`: process alive.
- `GET /health/ready`: PostgreSQL schema and Firestore reachable.
- `GET /v1/products`: catalog and remaining stock.
- `POST /v1/orders`: create or replay one order.
- `GET /v1/orders/{id}`: inspect its saved status.

After confirming an order, run the one-shot worker:

```bash
gcloud run jobs execute flashcart-worker-dev --project=ritru-fc-dev-01 --region=asia-south1 --wait
```

Inspect `invoices/<order-id>.json` in the existing private invoices bucket and
pull a message from `flashcart-order-events-dev-inspect`. The stored JSON is an
order summary, not a tax invoice. Events are at least once; use the event ID to
understand consumer deduplication. No payment or shipment has occurred.

## File reading order

1. Backend `src/flashcart/api.py`: endpoints.
2. Backend `service.py`, `postgres.py`, `firestore.py`: order and retry behavior.
3. Backend `worker.py` and `cloud.py`: order summaries and events.
4. Backend `cloudrun.py` and `migrate.py`: private SQL proxy and explicit bootstrap.
5. Backend `.github/workflows/ci.yml` then `image.yml`: test/build/publish.
6. Infra `stacks/04-backend/`: identities, secrets, events, services/jobs and outputs.
7. Infra `.github/workflows/backend-dev.yml`: plan and approval-gated deployment.

For the foundation, read the existing network/data stacks and the earlier
registry stack separately. Deployment of those stacks is not part of this demo.

## Cross-project identity and API quota

The workflow identity is hosted in `ritru-tf-seed-01`, while application resources
belong to `ritru-fc-dev-01`. The backend Google provider explicitly sets
`billing_project` to the dev project and enables `user_project_override` so API
quota/service enablement is evaluated there. Its identities need
`serviceusage.services.use` in dev. Otherwise Cloud SQL/Pub/Sub can report that
an API is disabled in the identity project even when it is enabled in dev.

Before the first backend plan, ensure the dev control-plane APIs are enabled:

```bash
gcloud services enable iam.googleapis.com cloudresourcemanager.googleapis.com --project=ritru-fc-dev-01
```

The existing foundation already enabled the workload APIs. Enabling these APIs
does not create SQL instances or other workloads; it allows explicitly dev-billed
identity/permission metadata requests.

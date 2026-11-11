# FlashCart GCP Infra (`gcp/02-flashcart-serverless-saga`)

Enterprise multi-environment Terraform repository for the **FlashCart Serverless E-Commerce & Saga Engine** on Google Cloud.

## Current Status
- **Completed & Modularized:**
  - `modules/vpc-network` + `stacks/01-network` (14 GCP APIs, custom regional VPC, Direct VPC Egress subnet, PSA `/20` peering, Cloud Router + NAT, IAP-only SSH firewall)
  - `modules/data-tier` + `stacks/02-data` (Firestore Native with PITR, Pub/Sub Avro schema + topic + DLQ, Cloud SQL PostgreSQL 16 private-IP with IAM Auth, hardened GCS invoices bucket)
  - Shared `.github/workflows/` (`infra.yml`, `terraform-stack.yml`, `drift.yml`), OPA Conftest `policies/*.rego`, `.tflint.hcl`, `.pre-commit-config.yaml`, `scripts/tf.sh`, `scripts/nuke-check.sh`
- **Remaining Stacks to Build Next:**
  - `stacks/03-app` (Artifact Registry, per-service SAs, Cloud SQL IAM DB users, Cloud Run `checkout-api`, `catalog-read-svc`, `inventory-svc`, Cloud Workflows `order-saga`, Eventarc trigger)
  - `stacks/04-edge` (Serverless NEGs, Cloud Armor WAF + rate limiting, Cloud CDN on catalog, Global External ALB + optional Google-managed TLS)
  - `stacks/05-extras` (Cloud Deploy canary pipeline + Monitoring alerts, Zero-ETL BigQuery Pub/Sub subscription, Cloud Run Jobs `outbox-relay` + `fulfillment-job`, Cloud Scheduler, OTel Secret, optional AlloyDB)

## Fork qualification: dev-only PR planning

This fork currently qualifies **only** `stacks/03-application` with
`env/dev.tfvars` in `ritru-fc-dev-01`. The expected plan creates one immutable-tag
Docker repository, `flashcart-docker`, in `asia-south1`. Network and data stacks
are intentionally excluded from this PR's planning.

```text
same-repository feat/flashcart-artifact-registry PR -> main
  -> fixed dev Artifact Registry stack
  -> keyless, read-only plan identity
  -> format / validate / lint / plan / OPA / resource scope checks
  -> allowlisted review summary; no apply job
```

There is no push trigger or manual Terraform trigger. Drift scanning is paused.
Staging/prod jobs, apply inputs, deployment credentials, and saved plan uploads
are absent. Plans run with `-lock=false` because this identity cannot write state
or lock objects. Counts and allowlisted resource details appear in the Actions
job summary; raw plans, state, and OIDC credential files are not published.
A deployment must produce and review a fresh plan after separate authorization;
this PR's read-only snapshot must not be reused for apply.

### Connected settings

| Repository variable | Value |
| --- | --- |
| `GCP_WIF_PROVIDER` | `projects/586582398977/locations/global/workloadIdentityPools/flashcart-dev-pr/providers/github-pr` |
| `GCP_PLAN_SA` | `flashcart-dev-pr-plan@ritru-tf-seed-01.iam.gserviceaccount.com` |
| `GCP_STATE_BUCKET` | `ritru-tfstate-586582398977` |
| `TF_STATE_PREFIX` | `gcp-02-flashcart` |

`GCP_APPLY_SA` is deliberately not configured. These variables are identifiers,
not credentials; no service-account key is needed.

The separate WIF pool/provider checks numeric repository ID `1453724177`, owner
ID `334222478`, repository name, PR event, `main` base, the exact feature branch,
and the `infra.yml` PR merge ref. Other branches, pushes, scheduled runs, and the
upstream repository do not meet this provider's trust condition. The workflow
also rejects forks before requesting cloud authentication.

The plan account has `roles/artifactregistry.reader` in the dev project. Its
conditional `roles/storage.objectViewer` bucket grant allows object reads only
under `gcp-02-flashcart/stacks/03-application/dev/`. GCS backend workspace discovery
also requires bucket-level object listing; object names elsewhere in this shared
bucket can therefore be listed, but their contents cannot be read with this
grant. There are no state write or lock permissions. Existing upstream identities
and trust were left unchanged.

The default branch still contains the old workflows until this PR is merged.
The newly configured WIF provider rejects their push/manual/scheduled events,
and this fork has no apply identity configured. Do not merge or authorize an
apply until the actual PR plan and its checks have been reviewed. Any future
apply or promotion workflow requires a separate design and explicit approval.

### Local validation without cloud access

```bash
terraform fmt -check -recursive modules/application-tier stacks/03-application
terraform -chdir=stacks/03-application init -backend=false
terraform -chdir=stacks/03-application validate
```

Do not use the legacy local helper's apply/destroy commands during qualification.

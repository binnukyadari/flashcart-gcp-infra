# Dev Artifact Registry: manual plan and approval

## Current boundary

Preparation only. No merge, workflow dispatch, environment approval, remote state
initialization, registry creation or deployment has been performed as part of
this preparation. PR #1 remains the review surface. A fresh PR plan and offline
safety tests qualify the proposed source; the main-only dispatch and apply path
cannot be qualified live before a separately authorized merge and run.

The application target is fixed: `stacks/03-application`, `env/dev.tfvars`, project
`ritru-fc-dev-01`, region `asia-south1`, repository `flashcart-docker`, DOCKER with
immutable tags. There are no stack/environment inputs or staging/prod paths.

## Flow

```text
PR: infra.yml -> safety tests + terraform-stack.yml -> read-only dev plan

After an authorized merge:
manual deploy-dev.yml on main
  -> terraform-stack.yml: read-only snapshot, validation, lint, plan, OPA
  -> display safe resource details, source SHA and plan fingerprint
  -> apply job only if deploy=true, exact confirmation text, apply switch=true,
     and the plan creates exactly one allowed resource
  -> required dev-artifact-registry environment review by binnukyadari
  -> verify source is still main and reviewed plan age <= 1 hour
  -> authenticate as separate apply identity (not provisioned yet)
  -> initialize exact remote dev backend and generate a new saved plan
  -> repeat policies/scope checks and compare all resource/output changes
     and drift with the reviewed fingerprint
  -> recheck source and age; apply that same saved plan; verify outputs
```

Nothing runs on pushes or merges automatically. Plan-only manual runs use the
`deploy=false` default. An approved job that detects a changed source, expired
review, changed plan, unexpected resource, update, deletion, move/import,
incomplete plan or mutable tags stops. No old snapshot plan is applied.
Deployment runs are serialized and do not cancel one another. Terraform's own
remote state locking and stale-plan protection remain enabled for apply.

## Configured now

- GitHub identity/reviewer: `binnukyadari`, user ID `334222478`.
- Environment: `dev-artifact-registry`, required reviewer `binnukyadari`;
  custom deployment branch policy allows the `main` branch only.
- Self-review is allowed so the sole named account can manually dispatch and
  later review. This is a human approval gate, not a two-person separation.
  Repository administrators retain GitHub's environment administration powers.
- Repository switch `FLASHCART_DEV_APPLY_ENABLED=false`.
- `GCP_MANUAL_PLAN_WIF_PROVIDER` points to
  `projects/586582398977/locations/global/workloadIdentityPools/flashcart-dev-pr/providers/github-manual-plan`.
- Manual plan WIF requires numeric repository and owner IDs, exact repository,
  workflow_dispatch event, main ref/subject, exact deploy-dev.yml caller and
  terraform-stack.yml reusable workflow on main.
- The existing PR provider remains PR-only. Both providers can impersonate only
  the existing read-only plan account, with dev Artifact Registry reader and
  get access to the exact application dev state object. No list/state writes.

## Deliberately unconfigured until deployment authorization

`GCP_DEV_APPLY_WIF_PROVIDER` and `GCP_DEV_APPLY_SA` are absent. The proposed apply
pool `flashcart-dev-apply` and account
`flashcart-dev-ar-apply@ritru-tf-seed-01.iam.gserviceaccount.com` have not been
provisioned. No write grants are added during preparation. Do not reuse the
upstream owner-level apply account.

Before an authorized deployment, provision the separate apply pool/account with:

1. Trust limited to numeric repository `1453724177`, owner `334222478`, exact
   repository, workflow_dispatch, refs/heads/main, exact deploy-dev.yml on main,
   and subject `repo:binnukyadari/flashcart-gcp-infra:environment:dev-artifact-registry`.
   Only the apply account may be impersonated through that pool.
2. Dev-only custom permissions needed to create/get the registry, without
   repository delete or broad Owner/Editor/Artifact Registry Admin access.
   Validate actual API permission needs before declaring the apply path ready.
3. Remote state object/lock permissions restricted to
   `gcp-02-flashcart/stacks/03-application/dev/`; GCS workspace discovery may
   require bucket-level object-name listing. Review that metadata exposure
   before granting it. Keep all other state contents excluded.
4. Environment-scoped apply provider/account variables with the exact names
   expected by the workflow. Set the repository apply switch to true only after
   explicit deployment authorization. Do not approve the environment as agent.

Then use a fresh main-only manual run with deploy requested and confirmation
`ritru-fc-dev-01/flashcart-docker`. Review its plan summary and fingerprint before
human environment approval. More than one hour of waiting requires a new run.

## Evidence and limits

PR checks run the actual cloud read-only plan and policy checks plus Python tests
for rejected targets/actions, plan fingerprint changes, stale/future approvals,
missing versus inaccessible state, and workflow gates. Syntax validation uses
actionlint. No test executes terraform apply or grants write access. Raw plans,
state and credentials stay on the runner and are cleaned up; no saved-plan
artifact is uploaded. Full JSON changes are fingerprinted, not published.

A green PR is not evidence that main-only dispatch, environment waiting, remote
backend writes, apply IAM, or registry creation have succeeded. Those remain
separate, explicitly authorized qualification steps.

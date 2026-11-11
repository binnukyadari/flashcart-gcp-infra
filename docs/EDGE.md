# Dev HTTPS edge

All 16 edge resources are created in the private remote state. Temporary DNS
resolves to `136.82.74.122`; HTTP returns 301 to HTTPS. IAP is enabled, the IAP
service identity has Cloud Run invoker access, trainer-only IAP access is set,
and Cloud Armor is attached. Managed TLS is ACTIVE and the HTTPS endpoint
redirects an anonymous request to Google sign-in.

Training URL: `https://flashcart-136-82-74-122.sslip.io`.

Local validation and all 18 existing deployment safety tests passed. Provider
checksums cover Linux CI and macOS. Initial creation saved 15 resources before
IAP identity propagation delayed its invoker binding. After explicitly creating
the IAP service identity, a new saved plan contained only the one missing binding;
it applied successfully without changing or deleting the saved resources.

- Project: `ritru-fc-dev-01`; serverless NEG region: `asia-south1`.
- State prefix: `gcp-02-flashcart/stacks/05-edge/dev`.
- Temporary hostname: `flashcart-<IPv4-with-dashes>.sslip.io`. Public wildcard DNS
  is operated by a third party. It requires no owned domain or Cloud DNS zone.
  Use an owned domain for a durable deployment. TLS provisioning can take time.
- HTTPS forwarding on 443; HTTP on 80 redirects to HTTPS. TLS 1.2 minimum.
- Cloud Armor: sensitivity-1 SQL injection and XSS rules, 120 requests/IP/minute
  throttle with HTTP 429 above the threshold. This is not a production tuning
  claim; shared NATs can hit the same limit.
- IAP uses a Google-managed OAuth client and grants access only to
  `contact@ritru.com`. Cloud Run invocation is granted to the IAP service agent;
  no anonymous invoker is added. The existing trainer invoker is preserved.
- API calls still require the training API key. Never put it in this document,
  repository, URLs or screenshots. Enter it in the storefront only after valid
  HTTPS and Google sign-in. The browser stores it only in page memory.
- Cloud Run currently retains its existing IAM-protected direct endpoint.
  Restrict ingress to internal/load-balancer traffic only after edge access is
  verified; that change belongs to `04-backend` and its reviewed deployment gate.
- The global load balancer, public IP, Cloud Armor rules and request processing
  incur ongoing charges, even when the Cloud Run app scales to zero.

## Provision

Use the explicitly selected `contact@ritru.com` identity. Initialize Terraform
with the existing private state bucket and the edge prefix above, review the
saved plan, then apply that saved plan. This stack must only create the declared
edge resources; it must not recreate or import the running backend/data tier.
Never commit local plans, state, credentials or `.terraform` directories.

## Verify

1. The output hostname resolves to the reserved global IP.
2. The managed certificate becomes ACTIVE and a normal HTTPS request validates.
3. HTTP redirects to HTTPS; an anonymous HTTPS request reaches IAP sign-in.
4. Sign in as `contact@ritru.com`; open the storefront and enter the API key.
5. Check a synthetic order with a unique durable idempotency key.
6. Confirm the backend has the expected Cloud Armor policy and IAP enabled.
7. Verify denied WAF requests in load balancer logs before tuning rules.

Destroying this edge stack removes the training URL, not the data/back-end
stacks. Review a destroy plan and obtain explicit authorization first. Disable
API deletion and preserve shared resources. The existing private proxy continues
working until backend ingress hardening is separately approved and applied.

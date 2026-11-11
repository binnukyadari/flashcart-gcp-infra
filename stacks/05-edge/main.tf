locals {
  project = "ritru-fc-dev-01"
  region  = "asia-south1"
  # Temporary wildcard DNS
  # Replace with an owned domain for long-term use.
  hostname = "flashcart-${replace(google_compute_global_address.edge.address, ".", "-")}.sslip.io"
}
resource "google_project_service" "iap" {
  project            = local.project
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}
resource "google_project_service_identity" "iap" {
  provider   = google-beta
  project    = local.project
  service    = "iap.googleapis.com"
  depends_on = [google_project_service.iap]
}
resource "google_compute_global_address" "edge" {
  project = local.project
  name    = "flashcart-dev-edge"
}
resource "google_compute_region_network_endpoint_group" "api" {
  project               = local.project
  name                  = "flashcart-dev-api-neg"
  region                = local.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = "flashcart-api-dev"
  }
}
resource "google_compute_security_policy" "edge" {
  project     = local.project
  name        = "flashcart-dev-armor"
  description = "Dev training WAF and per-IP request throttling"
  rule {
    priority    = 1000
    action      = "deny(403)"
    description = "SQL injection WAF"
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})"
      }
    }
  }
  rule {
    priority    = 1001
    action      = "deny(403)"
    description = "Cross-site scripting WAF"
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 1})"
      }
    }
  }
  rule {
    priority    = 2000
    action      = "throttle"
    description = "Per-IP training traffic limit"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 120
        interval_sec = 60
      }
    }
  }
  rule {
    priority = 2147483647
    action   = "allow"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}
resource "google_compute_backend_service" "api" {
  project               = local.project
  name                  = "flashcart-dev-api-edge"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP"
  port_name             = "http"
  timeout_sec           = 30
  enable_cdn            = false
  security_policy       = google_compute_security_policy.edge.id
  backend {
    group = google_compute_region_network_endpoint_group.api.id
  }
  iap {
    enabled = true
  }
  log_config {
    enable      = true
    sample_rate = 1.0
  }
  depends_on = [google_project_service_identity.iap]
}
resource "google_cloud_run_v2_service_iam_member" "iap" {
  project  = local.project
  location = local.region
  name     = "flashcart-api-dev"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap.email}"
}
resource "google_iap_web_backend_service_iam_member" "trainer" {
  project             = local.project
  web_backend_service = google_compute_backend_service.api.name
  role                = "roles/iap.httpsResourceAccessor"
  member              = "user:contact@ritru.com"
}
resource "google_compute_managed_ssl_certificate" "edge" {
  project = local.project
  name    = "flashcart-dev-edge-cert"
  managed {
    domains = [local.hostname]
  }
}
resource "google_compute_ssl_policy" "edge" {
  project         = local.project
  name            = "flashcart-dev-edge-tls"
  min_tls_version = "TLS_1_2"
  profile         = "MODERN"
}
resource "google_compute_url_map" "https" {
  project         = local.project
  name            = "flashcart-dev-https"
  default_service = google_compute_backend_service.api.id
}
resource "google_compute_target_https_proxy" "edge" {
  project          = local.project
  name             = "flashcart-dev-https"
  url_map          = google_compute_url_map.https.id
  ssl_certificates = [google_compute_managed_ssl_certificate.edge.id]
  ssl_policy       = google_compute_ssl_policy.edge.id
}
resource "google_compute_global_forwarding_rule" "https" {
  project               = local.project
  name                  = "flashcart-dev-https"
  target                = google_compute_target_https_proxy.edge.id
  ip_address            = google_compute_global_address.edge.id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
resource "google_compute_url_map" "redirect" {
  project = local.project
  name    = "flashcart-dev-http-redirect"
  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}
resource "google_compute_target_http_proxy" "redirect" {
  project = local.project
  name    = "flashcart-dev-http-redirect"
  url_map = google_compute_url_map.redirect.id
}
resource "google_compute_global_forwarding_rule" "http" {
  project               = local.project
  name                  = "flashcart-dev-http-redirect"
  target                = google_compute_target_http_proxy.redirect.id
  ip_address            = google_compute_global_address.edge.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

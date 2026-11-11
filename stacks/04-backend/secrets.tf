resource "google_secret_manager_secret" "api_key" {
  project   = local.project
  secret_id = "flashcart-dev-api-key"
  replication {
    auto {}
  }
}
resource "google_secret_manager_secret_version" "api_key" {
  secret          = google_secret_manager_secret.api_key.id
  secret_data     = var.api_key
  deletion_policy = "ABANDON"
}
resource "google_secret_manager_secret_iam_member" "api_key" {
  for_each  = toset(["api", "worker"])
  project   = local.project
  secret_id = google_secret_manager_secret.api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime[each.key].email}"
}
resource "google_secret_manager_secret" "bootstrap" {
  project   = local.project
  secret_id = "flashcart-dev-bootstrap-db"
  replication {
    auto {}
  }
}
resource "google_secret_manager_secret_version" "bootstrap" {
  secret          = google_secret_manager_secret.bootstrap.id
  secret_data     = "postgresql://flashcart-bootstrap:${urlencode(var.bootstrap_password)}@127.0.0.1:5432/inventory?sslmode=disable"
  deletion_policy = "ABANDON"
}
resource "google_secret_manager_secret_iam_member" "bootstrap" {
  project   = local.project
  secret_id = google_secret_manager_secret.bootstrap.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime["bootstrap"].email}"
}

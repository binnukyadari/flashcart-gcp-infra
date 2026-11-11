locals {
  project      = "ritru-fc-dev-01"
  region       = "asia-south1"
  sql_instance = "flashcart-dev-inventory"
  connection   = "ritru-fc-dev-01:asia-south1:flashcart-dev-inventory"
  bucket       = "flashcart-dev-invoices-ritru-fc-dev-01"
  deployer     = "serviceAccount:flashcart-backend-apply@ritru-tf-seed-01.iam.gserviceaccount.com"
  roles = {
    api_database    = { account = "api", role = "roles/cloudsql.client" }
    api_login       = { account = "api", role = "roles/cloudsql.instanceUser" }
    api_orders      = { account = "api", role = "roles/datastore.user" }
    worker_database = { account = "worker", role = "roles/cloudsql.client" }
    worker_login    = { account = "worker", role = "roles/cloudsql.instanceUser" }
    worker_orders   = { account = "worker", role = "roles/datastore.user" }
    bootstrap_sql   = { account = "bootstrap", role = "roles/cloudsql.client" }
  }
  app_env = {
    FLASHCART_MODE               = "gcp"
    FLASHCART_PROJECT_ID         = local.project
    FLASHCART_SQL_INSTANCE       = local.connection
    FLASHCART_FIRESTORE_DATABASE = "(default)"
    FLASHCART_PUBSUB_TOPIC       = "projects/ritru-fc-dev-01/topics/flashcart-order-events-v1"
    FLASHCART_INVOICE_BUCKET     = local.bucket
  }
}
resource "google_service_account" "runtime" {
  for_each     = toset(["api", "worker", "bootstrap"])
  project      = local.project
  account_id   = "flashcart-${each.key}"
  display_name = "FlashCart dev ${each.key}"
}
resource "google_project_iam_member" "runtime" {
  for_each = local.roles
  project  = local.project
  role     = each.value.role
  member   = "serviceAccount:${google_service_account.runtime[each.value.account].email}"
}
resource "google_service_account_iam_member" "deployer" {
  for_each           = google_service_account.runtime
  service_account_id = each.value.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.deployer
}
resource "google_sql_user" "runtime" {
  for_each = toset(["api", "worker"])
  project  = local.project
  instance = local.sql_instance
  name     = trimsuffix(google_service_account.runtime[each.key].email, ".gserviceaccount.com")
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}
resource "google_sql_user" "bootstrap" {
  project  = local.project
  instance = local.sql_instance
  name     = "flashcart-bootstrap"
  type     = "BUILT_IN"
  password = var.bootstrap_password
}
resource "google_project_iam_custom_role" "invoice_writer" {
  project     = local.project
  role_id     = "flashcartInvoiceWriter"
  title       = "FlashCart invoice object create and read"
  description = "No object delete, overwrite or bucket listing permissions."
  permissions = ["storage.objects.create", "storage.objects.get"]
}
resource "google_storage_bucket_iam_member" "worker" {
  bucket = local.bucket
  role   = google_project_iam_custom_role.invoice_writer.name
  member = "serviceAccount:${google_service_account.runtime["worker"].email}"
  condition {
    title       = "flashcart_invoice_objects"
    description = "Only the immutable invoice artifacts prefix."
    expression  = "resource.name.startsWith('projects/_/buckets/${local.bucket}/objects/invoices/')"
  }
}

# Preserve the existing legacy orders-created-v1 schema and topic.
resource "google_pubsub_schema" "events" {
  project = local.project
  name    = "flashcart-order-event-v1"
  type    = "AVRO"
  definition = jsonencode({
    type = "record", name = "FlashCartOrderEventV1", fields = [
      { name = "id", type = "string" },
      { name = "type", type = "string" },
      { name = "order_id", type = "string" },
      { name = "occurred_at", type = "string" },
      { name = "schema_version", type = "int" },
    ]
  })
}
resource "google_pubsub_topic" "events" {
  project                    = local.project
  name                       = "flashcart-order-events-v1"
  message_retention_duration = "86400s"
  schema_settings {
    schema   = google_pubsub_schema.events.id
    encoding = "JSON"
  }
}
resource "google_pubsub_subscription" "inspect" {
  project                    = local.project
  name                       = "flashcart-order-events-dev-inspect"
  topic                      = google_pubsub_topic.events.id
  message_retention_duration = "86400s"
  ack_deadline_seconds       = 30
}
resource "google_pubsub_topic_iam_member" "worker" {
  project = local.project
  topic   = google_pubsub_topic.events.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.runtime["worker"].email}"
}

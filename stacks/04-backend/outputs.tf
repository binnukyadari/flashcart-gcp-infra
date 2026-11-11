output "api_url" { value = google_cloud_run_v2_service.api.uri }
output "worker_job" { value = google_cloud_run_v2_job.worker.name }
output "bootstrap_job" { value = google_cloud_run_v2_job.bootstrap.name }
output "event_topic" { value = google_pubsub_topic.events.id }
output "event_subscription" { value = google_pubsub_subscription.inspect.id }

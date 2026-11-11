resource "google_artifact_registry_repository" "docker" {
  project       = var.project_id
  location      = var.region
  repository_id = "${var.project}-docker"
  description   = "Docker images for the FlashCart application"
  format        = "DOCKER"

  docker_config {
    immutable_tags = true
  }
}

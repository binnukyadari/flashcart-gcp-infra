output "artifact_registry_repository_id" {
  description = "Artifact Registry repository ID."
  value       = module.application.repository_id
}

output "artifact_registry_repository_url" {
  description = "Docker repository URL for pushing application images."
  value       = module.application.repository_url
}

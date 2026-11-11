variable "project_id" {
  description = "GCP project ID for this environment."
  type        = string
}

variable "project" {
  description = "Workload name prefix."
  type        = string
  default     = "flashcart"
}

variable "environment" {
  description = "Target environment (dev, staging, prod)."
  type        = string
}

variable "region" {
  description = "GCP region."
  type        = string
  default     = "asia-south1"
}

variable "owner" {
  description = "Owning team label."
  type        = string
}

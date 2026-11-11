variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "project" {
  description = "Workload name prefix."
  type        = string
  default     = "flashcart"
}

variable "region" {
  description = "GCP region for application resources."
  type        = string
  default     = "asia-south1"
}

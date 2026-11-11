variable "backend_image" {
  description = "Tested linux/amd64 backend image, pinned to its Artifact Registry digest."
  type        = string
  validation {
    condition     = can(regex("^asia-south1-docker\\.pkg\\.dev/ritru-fc-dev-01/flashcart-docker/backend@sha256:[a-f0-9]{64}$", var.backend_image))
    error_message = "Use the tested backend image digest in the existing dev registry."
  }
}
variable "api_key" {
  description = "Trusted-client training API key; supplied through a GitHub secret."
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.api_key) >= 32
    error_message = "Use a randomly generated API key of at least 32 characters."
  }
}
variable "bootstrap_password" {
  description = "Dedicated schema-bootstrap SQL user's password, not the existing postgres user."
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.bootstrap_password) >= 32
    error_message = "Use a randomly generated bootstrap password of at least 32 characters."
  }
}

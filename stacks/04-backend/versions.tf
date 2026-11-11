terraform {
  required_version = ">= 1.11"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }
}
provider "google" {
  project               = "ritru-fc-dev-01"
  region                = "asia-south1"
  billing_project       = "ritru-fc-dev-01"
  user_project_override = true
  default_labels = {
    project     = "flashcart"
    environment = "dev"
    owner       = "platform-team"
    stack       = "04-backend"
    managed-by  = "terraform"
  }
}

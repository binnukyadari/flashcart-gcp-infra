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
  project = var.project_id
  region  = var.region

  default_labels = {
    project     = var.project
    environment = var.environment
    owner       = var.owner
    stack       = "03-application"
    managed-by  = "terraform"
  }
}

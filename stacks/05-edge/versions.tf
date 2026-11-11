terraform {
  required_version = ">= 1.11"
  required_providers {
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 8.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }
  backend "gcs" {}
}
provider "google" {
  project               = "ritru-fc-dev-01"
  region                = "asia-south1"
  billing_project       = "ritru-fc-dev-01"
  user_project_override = true
  default_labels = {
    project     = "flashcart"
    environment = "dev"
    stack       = "05-edge"
    managed-by  = "terraform"
  }
}

provider "google-beta" {
  project               = "ritru-fc-dev-01"
  region                = "asia-south1"
  billing_project       = "ritru-fc-dev-01"
  user_project_override = true
}

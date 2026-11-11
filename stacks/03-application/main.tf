module "application" {
  source = "../../modules/application-tier"

  project_id = var.project_id
  project    = var.project
  region     = var.region
}

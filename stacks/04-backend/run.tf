resource "google_cloud_run_v2_service" "api" {
  project             = local.project
  location            = local.region
  name                = "flashcart-api-dev"
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"
  template {
    service_account                  = google_service_account.runtime["api"].email
    timeout                          = "30s"
    max_instance_request_concurrency = 8
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = "flashcart-dev"
        subnetwork = "flashcart-dev-run"
      }
    }
    containers {
      name    = "api"
      image   = var.backend_image
      command = ["python", "-m", "flashcart.cloudrun"]
      args    = ["api"]
      ports { container_port = 8080 }
      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      startup_probe {
        initial_delay_seconds = 2
        period_seconds        = 2
        failure_threshold     = 30
        http_get { path = "/health/live" }
      }
      dynamic "env" {
        for_each = local.app_env
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name  = "FLASHCART_DATABASE_URL"
        value = "postgresql://${urlencode(google_sql_user.runtime["api"].name)}@127.0.0.1:5432/inventory?sslmode=disable"
      }
      env {
        name = "FLASHCART_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_key.secret_id
            version = google_secret_manager_secret_version.api_key.version
          }
        }
      }
    }
  }
  depends_on = [google_project_iam_member.runtime, google_service_account_iam_member.deployer, google_secret_manager_secret_iam_member.api_key]
}
resource "google_cloud_run_v2_service_iam_member" "trainer" {
  project  = local.project
  location = local.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "user:contact@ritru.com"
}
resource "google_cloud_run_v2_job" "worker" {
  project             = local.project
  location            = local.region
  name                = "flashcart-worker-dev"
  deletion_protection = true
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.runtime["worker"].email
      timeout         = "300s"
      max_retries     = 0
      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = "flashcart-dev"
          subnetwork = "flashcart-dev-run"
        }
      }
      containers {
        name    = "worker"
        image   = var.backend_image
        command = ["python", "-m", "flashcart.cloudrun"]
        args    = ["worker"]
        resources { limits = { cpu = "1", memory = "512Mi" } }
        dynamic "env" {
          for_each = local.app_env
          content {
            name  = env.key
            value = env.value
          }
        }
        env {
          name  = "FLASHCART_DATABASE_URL"
          value = "postgresql://${urlencode(google_sql_user.runtime["worker"].name)}@127.0.0.1:5432/inventory?sslmode=disable"
        }
        env {
          name = "FLASHCART_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.api_key.secret_id
              version = google_secret_manager_secret_version.api_key.version
            }
          }
        }
      }
    }
  }
  depends_on = [google_project_iam_member.runtime, google_service_account_iam_member.deployer, google_secret_manager_secret_iam_member.api_key, google_storage_bucket_iam_member.worker, google_pubsub_topic_iam_member.worker]
}
resource "google_cloud_run_v2_job" "bootstrap" {
  project             = local.project
  location            = local.region
  name                = "flashcart-bootstrap-dev"
  deletion_protection = true
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.runtime["bootstrap"].email
      timeout         = "300s"
      max_retries     = 0
      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = "flashcart-dev"
          subnetwork = "flashcart-dev-run"
        }
      }
      containers {
        name    = "bootstrap"
        image   = var.backend_image
        command = ["python", "-m", "flashcart.cloudrun"]
        args    = ["migrate"]
        resources { limits = { cpu = "1", memory = "512Mi" } }
        env {
          name  = "FLASHCART_SQL_INSTANCE"
          value = local.connection
        }
        env {
          name = "FLASHCART_BOOTSTRAP_DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.bootstrap.secret_id
              version = google_secret_manager_secret_version.bootstrap.version
            }
          }
        }
      }
    }
  }
  depends_on = [google_project_iam_member.runtime, google_service_account_iam_member.deployer, google_sql_user.bootstrap, google_sql_user.runtime, google_secret_manager_secret_iam_member.bootstrap]
}

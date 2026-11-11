output "url" { value = "https://${local.hostname}" }
output "ip_address" { value = google_compute_global_address.edge.address }
output "access" { value = "Google IAP: contact@ritru.com only; application API key also required" }

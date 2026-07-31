output "gcp_user" {
  description = "The user registered in the compute instances. This data is used later in the experiments"
  value       = var.gcp_user
}

output "gcp_private_key_filepath" {
  value       = var.gcp_private_key_filepath
  description = "The private key used to log into compute instances. This data is used later in the experiments"
}

output "load_instance_private_ip" {
  value = google_compute_instance.load_instance.network_interface.0.network_ip
}

output "load_instance_public_ip" {
  value = google_compute_instance.load_instance.network_interface.0.access_config.0.nat_ip
}

output "ol_instance_private_ip" {
  value = google_compute_instance.openlambda_instance.network_interface.0.network_ip
}


output "ol_instance_public_ip" {
  value = google_compute_instance.openlambda_instance.network_interface.0.access_config.0.nat_ip
}

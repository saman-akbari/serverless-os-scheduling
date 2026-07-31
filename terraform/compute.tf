resource "google_compute_instance" "openlambda_instance" {
  name         = "openlambda-instance"
  machine_type = "e2-highmem-8"

  boot_disk {
    initialize_params {
      //image = "ubuntu-2504-plucky-amd64-v20250508"
      //image = "ubuntu-2204-jammy-v20251120"
      image = var.OPEN_LAMBDA_IMAGE
      size  = 50
    }
  }

  network_interface {
    network = google_compute_network.vpc_network.id
    access_config {
    }
  }

  metadata = {
    ssh-keys = format("%s:%s", var.gcp_user, file(var.gcp_public_key_filepath))
  }
}

resource "google_compute_instance" "load_instance" {
  depends_on   = [google_compute_instance.openlambda_instance]
  name         = "load-instance"
  machine_type = "e2-micro"

  boot_disk {
    initialize_params {
      image = "ubuntu-2504-plucky-amd64-v20250508"
    }
  }

  network_interface {
    network = google_compute_network.vpc_network.id
    access_config {
    }
  }

  metadata = {
    ssh-keys = format("%s:%s", var.gcp_user, file(var.gcp_public_key_filepath)),
    ol-ip    = google_compute_instance.openlambda_instance.network_interface.0.network_ip
  }
}

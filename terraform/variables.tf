variable "gcp_project_id" {
  type = string
}

variable "gcp_region" {
  type = string
}

variable "gcp_zone" {
  type = string
}

variable "gcp_user" {
  type = string
}

variable "gcp_private_key_filepath" {
  type = string
}

variable "gcp_public_key_filepath" {
  type = string
}

variable "OPEN_LAMBDA_IMAGE" {
  type    = string
  default = "ubuntu-2204-jammy-v20220420"
}


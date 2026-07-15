variable "environment" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "redis_url" {
  type      = string
  sensitive = true
}

variable "api_image" {
  type = string
}

variable "api_key" {
  type      = string
  sensitive = true
}

variable "temporal_host" {
  type = string
}

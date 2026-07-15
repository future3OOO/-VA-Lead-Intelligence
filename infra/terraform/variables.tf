variable "aws_region" {
  description = "AWS region for the deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "va-lead-intelligence"
}

variable "database_name" {
  description = "Name of the application database"
  type        = string
  default     = "va_lead_intelligence"
}

variable "database_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "api_image" {
  description = "Container image for the FastAPI service"
  type        = string
}

variable "api_key" {
  description = "API key for basic workspace authentication"
  type        = string
  sensitive   = true
}

variable "temporal_host" {
  description = "Temporal server host:port"
  type        = string
  default     = "temporal:7233"
}

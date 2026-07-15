terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.22"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "networking" {
  source = "./modules/networking"

  environment = var.environment
  name_prefix = var.name_prefix
}

module "database" {
  source = "./modules/database"

  environment    = var.environment
  name_prefix    = var.name_prefix
  vpc_id         = module.networking.vpc_id
  subnet_ids     = module.networking.private_subnet_ids
  database_name  = var.database_name
  instance_class = var.database_instance_class
}

module "cache" {
  source = "./modules/cache"

  environment = var.environment
  name_prefix = var.name_prefix
  vpc_id      = module.networking.vpc_id
  subnet_ids  = module.networking.private_subnet_ids
}

module "api" {
  source = "./modules/api"

  environment   = var.environment
  name_prefix   = var.name_prefix
  vpc_id        = module.networking.vpc_id
  subnet_ids    = module.networking.private_subnet_ids
  database_url  = module.database.database_url
  redis_url     = module.cache.redis_url
  api_image     = var.api_image
  api_key       = var.api_key
  temporal_host = var.temporal_host
}

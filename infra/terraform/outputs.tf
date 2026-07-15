output "api_url" {
  description = "URL of the deployed FastAPI service"
  value       = module.api.load_balancer_dns
}

output "database_url" {
  description = "Application database URL"
  value       = module.database.database_url
  sensitive   = true
}

output "redis_url" {
  description = "Redis cache URL"
  value       = module.cache.redis_url
  sensitive   = true
}

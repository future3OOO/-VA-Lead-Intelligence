output "redis_url" {
  value     = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0"
  sensitive = true
}

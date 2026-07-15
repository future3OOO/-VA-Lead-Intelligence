resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.name_prefix}-cache-subnet-group"
  subnet_ids = var.subnet_ids
}

resource "aws_elasticache_cluster" "main" {
  cluster_id         = "${var.name_prefix}-cache"
  engine             = "redis"
  node_type          = "cache.t4g.micro"
  num_cache_nodes    = 1
  port               = 6379
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.cache.id]
}

resource "aws_security_group" "cache" {
  name   = "${var.name_prefix}-cache-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }
}

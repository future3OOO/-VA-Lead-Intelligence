output "database_url" {
  value     = "postgresql://${aws_db_instance.main.username}:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/${aws_db_instance.main.db_name}"
  sensitive = true
}

# Environment Variable Catalogue

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | False | `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres` |  |
| `REDIS_URL` | False | `redis://localhost:6379/0` |  |
| `TEMPORAL_HOST` | False | `localhost:7233` |  |
| `API_KEY` | False | `dev-api-key` |  |
| `LOG_LEVEL` | False | `INFO` |  |
| `ENVIRONMENT` | False | `development` |  |
| `TF_VAR_environment` | True | `` |  |
| `TF_VAR_name_prefix` | True | `` |  |
| `TF_VAR_vpc_id` | True | `` |  |
| `TF_VAR_subnet_ids` | True | `` |  |
| `TF_VAR_database_url` | True | `` |  |
| `TF_VAR_redis_url` | True | `` |  |
| `TF_VAR_api_image` | True | `` |  |
| `TF_VAR_api_key` | True | `` |  |
| `TF_VAR_temporal_host` | True | `` |  |
| `TF_VAR_environment` | True | `` |  |
| `TF_VAR_name_prefix` | True | `` |  |
| `TF_VAR_vpc_id` | True | `` |  |
| `TF_VAR_subnet_ids` | True | `` |  |
| `TF_VAR_environment` | True | `` |  |
| `TF_VAR_name_prefix` | True | `` |  |
| `TF_VAR_vpc_id` | True | `` |  |
| `TF_VAR_subnet_ids` | True | `` |  |
| `TF_VAR_database_name` | True | `` |  |
| `TF_VAR_instance_class` | True | `` |  |
| `TF_VAR_environment` | True | `` |  |
| `TF_VAR_name_prefix` | True | `` |  |
| `TF_VAR_aws_region` | False | `"us-east-1"` | AWS region for the deployment |
| `TF_VAR_environment` | False | `"production"` | Environment name |
| `TF_VAR_name_prefix` | False | `"va-lead-intelligence"` | Prefix for resource names |
| `TF_VAR_database_name` | False | `"va_lead_intelligence"` | Name of the application database |
| `TF_VAR_database_instance_class` | False | `"db.t4g.micro"` | RDS instance class |
| `TF_VAR_api_image` | True | `` | Container image for the FastAPI service |
| `TF_VAR_api_key` | True | `` | API key for basic workspace authentication |
| `TF_VAR_temporal_host` | False | `"temporal:7233"` | Temporal server host:port |

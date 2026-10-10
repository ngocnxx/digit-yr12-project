# The digit-yr12 app: the static site, the API as a container image in ECR, and the S3 object that holds the data.
# The values that differ by environment are in <environment>.tfvars.json; the account's values arrive as -var from the
# repository variables (docs/deploy.md).
terraform {
  required_version = ">= 1.11, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.28, < 7.0"
    }
  }

  # bucket, key and region arrive as -backend-config (docs/deploy.md); the state lives apart from every other root.
  backend "s3" {
    use_lockfile = true
    encrypt      = true
  }
}

variable "account_id" {
  type        = string
  description = "AWS account for this environment."
}

variable "region" {
  type        = string
  description = "AWS Region for this environment. There is no default."
}

variable "environment" {
  type        = string
  description = "dev or production."
}

variable "permissions_boundary_arn" {
  type        = string
  description = "The permissions boundary the account baseline made for this environment."
}

variable "alarm_topic_arn" {
  type        = string
  description = "SNS topic that receives alarm notifications."
}

variable "image_uri" {
  type        = string
  description = "The API image in ECR, pinned by digest: <repository>@sha256:<64 hex>."
}

variable "memory_mb" {
  type        = number
  default     = 512
  description = "Memory of the API function."
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]

  default_tags {
    tags = { service = "digit-yr12", environment = var.environment }
  }
}

module "app" {
  source = "git::https://github.com/nnthanh101/terraform-aws-serverless.git//modules/serverless-web-app?ref=c50e23437ce1b28f7db637f5bb6e7b6e9e760b36"

  account_id               = var.account_id
  region                   = var.region
  environment              = var.environment
  service                  = "digit-yr12"
  permissions_boundary_arn = var.permissions_boundary_arn
  alarm_topic_arn          = var.alarm_topic_arn

  image_uri            = var.image_uri
  architecture         = "arm64"
  memory_mb            = var.memory_mb
  secret_store         = "environment"
  reserved_concurrency = null
  site_source_dir      = "${path.module}/../../front-end"

  # The module adds S3DB_BUCKET and CORS_ORIGIN (the site's own address) and generates SECRET_KEY.
  environment_variables = {
    APP_ENV           = "production"
    DATABASE_PATH     = "/tmp/navigator.db"
    GUNICORN_CMD_ARGS = "--timeout 0 --workers 1 --threads 1"
  }
}

output "url" {
  description = "HTTPS address of the API."
  value       = module.app.url
}

output "site_url" {
  description = "HTTPS address of the site; it also serves /api."
  value       = module.app.site_url
}

output "function_name" {
  description = "The API function."
  value       = module.app.function_name
}

output "site_bucket" {
  description = "The bucket the pipeline uploads front-end/ to."
  value       = module.app.site_bucket
}

output "site_distribution_id" {
  description = "The CloudFront distribution the pipeline clears after an upload."
  value       = module.app.site_distribution_id
}

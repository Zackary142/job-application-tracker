terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # bucket/region passed in with -backend-config so no account ids in the repo
  # use_lockfile = s3 native locking, no dynamo lock table needed
  backend "s3" {
    key          = "main/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = var.project, ManagedBy = "terraform", Stack = "main" }
  }
}

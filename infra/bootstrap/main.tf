# run this once by hand - state bucket + oidc role for github actions
# state for this one is just local, it barely changes

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = var.project, ManagedBy = "terraform", Stack = "bootstrap" }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # newer repos get ids baked into the oidc sub: repo:owner@123/name@456:...
  # @* matches those ids (and the owner/name parts are still exact)
  gh_owner        = split("/", var.github_repo)[0]
  gh_name         = split("/", var.github_repo)[1]
  gh_repo_pattern = "${local.gh_owner}@*/${local.gh_name}@*"
}

resource "aws_s3_bucket" "state" {
  # bucket names are global so tack the account id on
  bucket = "${var.project}-tfstate-${local.account_id}"
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled" # so i can roll back if state gets messed up
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# oidc so no aws keys sitting in github secrets
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # aws doesnt actually check this anymore but the provider wants it
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # only the production env (deploy) and PRs (plan) from this repo
    # note: jobs with an environment get sub = ...:environment:<name>, not the branch
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        for s in ["environment:production", "pull_request"] : "repo:${local.gh_repo_pattern}:${s}"
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${var.project}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
}

# locked to job-tracker-* resources where possible
data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "TerraformState"
    actions   = ["s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
  }

  statement {
    sid     = "ProjectResources"
    actions = ["dynamodb:*", "lambda:*", "logs:*", "s3:*"]
    resources = [
      "arn:aws:dynamodb:${var.region}:${local.account_id}:table/${var.project}-*",
      "arn:aws:lambda:${var.region}:${local.account_id}:function:${var.project}-*",
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:*${var.project}-*",
      "arn:aws:s3:::${var.project}-frontend-*",
      "arn:aws:s3:::${var.project}-frontend-*/*",
    ]
  }

  statement {
    sid       = "ProjectIamRoles"
    actions   = ["iam:*Role*", "iam:PassRole", "iam:*RolePolicy*"]
    resources = ["arn:aws:iam::${local.account_id}:role/${var.project}-*"]
  }

  # apigw + cloudfront cant really be scoped by name so these are wide open. TODO tighten
  statement {
    sid       = "ApiGatewayAndCloudFront"
    actions   = ["apigateway:*", "cloudfront:*"]
    resources = ["*"]
  }

  # CreateUserPool doesn't support resource arns so this has to be *
  statement {
    sid       = "Cognito"
    actions   = ["cognito-idp:*"]
    resources = ["*"]
  }

  statement {
    sid       = "ReadOnlyLookups"
    actions   = ["logs:DescribeLogGroups", "sts:GetCallerIdentity"]
    resources = ["*"]
  }

  # apigw access logging uses these, they don't take a resource arn
  statement {
    sid = "ApiGatewayAccessLogs"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.deploy.json
}

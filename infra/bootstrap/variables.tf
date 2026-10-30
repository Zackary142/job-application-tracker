variable "project" {
  description = "Prefix for all resource names."
  type        = string
  default     = "job-tracker"
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "eu-west-2"
}

variable "github_repo" {
  description = "GitHub repository allowed to deploy, as owner/name."
  type        = string
}

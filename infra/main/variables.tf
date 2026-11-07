variable "project" {
  description = "Prefix for all resource names. Must match the bootstrap stack."
  type        = string
  default     = "job-tracker"
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "eu-west-2"
}

variable "lambda_zip_path" {
  description = "Path to the packaged API code, built by the pipeline."
  type        = string
  default     = "../../build/lambda.zip"
}

variable "log_retention_days" {
  description = "How long to keep Lambda and API Gateway logs."
  type        = number
  default     = 14
}

variable "extract_model" {
  description = "Bedrock model the job ad auto-fill uses."
  type        = string
  default     = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
}

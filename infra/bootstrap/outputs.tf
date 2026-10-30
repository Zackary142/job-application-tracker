output "state_bucket" {
  description = "Put this in the AWS_STATE_BUCKET GitHub variable."
  value       = aws_s3_bucket.state.bucket
}

output "github_actions_role_arn" {
  description = "Put this in the AWS_ROLE_ARN GitHub variable."
  value       = aws_iam_role.github_actions.arn
}

output "api_url" {
  value = aws_apigatewayv2_stage.default.invoke_url
}

output "frontend_url" {
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.frontend.id
}

# on demand = basically free when nobody's using it
resource "aws_dynamodb_table" "applications" {
  name         = "${var.project}-applications"
  billing_mode = "PAY_PER_REQUEST"

  # one partition per user, so a query only ever sees that user's items
  hash_key  = "user_id"
  range_key = "id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

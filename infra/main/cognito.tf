# user accounts. people sign up with email + password, cognito emails them a code
resource "aws_cognito_user_pool" "users" {
  name                     = "${var.project}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_uppercase = false
    require_symbols   = false
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

# the frontend's "app" in cognito. no client secret - it's a browser app so
# a secret couldn't be kept secret anyway
resource "aws_cognito_user_pool_client" "web" {
  name            = "${var.project}-web"
  user_pool_id    = aws_cognito_user_pool.users.id
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  # same error for "no such user" and "wrong password" so you can't
  # use the login form to find out who has an account
  prevent_user_existence_errors = "ENABLED"

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

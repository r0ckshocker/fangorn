provider "aws" {
  region = local.env_config.region
  default_tags {
    tags = local.env_config.default_tags
  }
  assume_role {
    role_arn = local.env_config.assume_role
  }
}

provider "aws" {
  alias  = "no-role"
  region = local.env_config.region
  default_tags {
    tags = local.env_config.default_tags
  }
}

provider "aws" {
  alias  = "us-east-1"
  region = "us-east-1"
  default_tags {
    tags = local.env_config.default_tags
  }
}

provider "aws" {
  # Configuration options
  alias  = "security"
  region = "us-east-2"
  default_tags {
    tags = local.env_config.default_tags
  }
  assume_role {
    role_arn = module.env_config.json.accounts.security.assume_role
  }
}

# provider "azurerm" {
#   features {}
# }

provider "cloudflare" {}

provider "okta" {
  base_url = "okta.com"
  org_name = "apprenticeio"
}
terraform {
  required_version = "> 1.3"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    sops = {
      source  = "carlpett/sops"
      version = "~> 0.6.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.9.0"
    }
    okta = {
      source  = "okta/okta"
      version = "~> 4.8.1"
    }
    # azurerm = {
    #   source  = "hashicorp/azurerm"
    #   version = "=3.0.0"
    # }
  }

  backend "s3" {
    encrypt        = true
    bucket         = "afs-infra-tf-state"
    dynamodb_table = "afs-terraform-state-lock-dynamo"
    region         = "us-east-1"
    key            = "afs-alfred.tfstate"
  }
}
module "env_config" {
  repository = "afs-sec"
  source     = "../../afs_tf_modules/env_config"
}

module "ecs_app" {
  account_config = module.env_config.account_vars
  containers     = local.containers
  env_config     = local.env_config
  ssm_config     = local.env_config
  target_groups  = local.target_groups
  source         = "../../afs_tf_modules/ecs_app"
  providers = {
    aws.no-role   = aws.no-role
    aws.us-east-1 = aws.us-east-1
  }
}

module "cf_tunnel" {
  env_region_state = data.terraform_remote_state.env_region.outputs
  env_config       = local.env_config
  source           = "./cf_tunnel"
  groups           = ["FTE", "Contractors", "Intern"]
}

module "okta_app" {
  source = "./okta_oauth"
  groups = ["FTE", "Contractors", "Intern"]
  app_name = "${local.name}.${local.domain}"
}

module "data_bucket" {
  source = "../../afs_tf_modules/s3"
  bucket = "afs-org-ose-alfred-data"
  notifications = true
  sns_topic     = local.lambdas.ask_alfred.sns_src
}

module "secrets" {
  env_config = local.env_config
  source     = "../../afs_tf_modules/secrets"
}

module "lambda" {
  source     = "../../afs_tf_modules/afs_ops_lambda"
  for_each   = { for f in local.functions : f.name => f }
  function   = each.value
  env_config = local.env_config
}







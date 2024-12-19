locals {
  cluster_id = data.terraform_remote_state.env_region.outputs["cluster_id"]
  containers = [
    {
      app_image_tag  = "latest"
      app_image_url  = "016897515115.dkr.ecr.us-east-1.amazonaws.com/afs_fangorn"
      container_port = 8080
      env_vars = {
        REDIRECT_URI         = "http://fangorn.apprenticefs.net/"
        ANTHROPIC_API_KEY    = data.sops_file.common.data.anthropic_api_key
        OPENAI_API_KEY       = data.sops_file.common.data.openai_api_key
        SECRET_KEY           = "quocisgreat"
        AWS_REGION           = local.env_config.region
        DATA_BUCKET          = module.data_bucket.id
        ENV_JSON_LAMBDA      = local.lambdas.env_config.lambda_arn
        DEVISION_LAMBDA      = local.lambdas.devision.lambda_arn
        LUCIUS_JSON_LAMBDA   = local.lambdas.ghas.lambda_arn
        DEVISION_GROUP       = "AFS_Security_Admin"
        ENVIRONMENT          = "production"
        CF_ACCESS_URL        = "https://apprenticefs.cloudflareaccess.com/cdn-cgi/access/get-identity"
      }
      name = "fangorn"
    }
  ]
  container_port = 8080
  domain         = "apprenticefs.net"
  env_config     = merge(module.env_config.vars, local.env_defaults)
  env_defaults = {
    app_count                 = 1
    api_enable                = true
    lambda_enable             = true
    cert_lookup               = false
    monitoring_enable         = false
    lb_enable                 = false
    container_name            = "fangorn"
    container_port            = 8080
    cloudflare_only           = true
    health_check_grace_period = null
    vpn_only                  = true
  }
  name          = "fangorn"
  target_groups = [module.cf_tunnel.tg]
  tunnel_sg     = module.cf_tunnel.sg
  lambdas       = data.terraform_remote_state.oracle.outputs.lambdas

  data_bucket = "afs-org-ose-fangorn-data"
  func_blocks = [
    {
      name     = "mongo_audit"
      trigger  = "cron"
      schedule = "cron(0/15 * ? * * *)"
      env_vars = {
        ATLAS_EVENT_KEY    = data.sops_file.common.data.atlas_event_key
        ATLAS_EVENT_SECRET = data.sops_file.common.data.atlas_event_secret
        DD_API_KEY         = data.sops_file.common.data.dd_api_key
        DD_APP_KEY         = data.sops_file.common.data.dd_app_key
        ATLAS_ORG_ID       = data.sops_file.common.data.atlas_org_id
        DD_SITE            = "datadoghq.com"
      }
    },
    {
      name     = "lucius"
      schedule = "cron(15 15 ? * MON-FRI *)" # 10:15am EST
      trigger  = "cron"
      env_vars = {
        DD_API_KEY        = data.sops_file.common.data.dd_signal_api_key
        DD_APP_KEY        = data.sops_file.common.data.dd_signal_app_key
        DD_SITE           = "datadoghq.com"
        NEWS_BOT_TOKEN    = data.sops_file.common.data.news_bot_token
        DATA_BUCKET       = local.data_bucket
        SLACK_CHANNEL_ID  = "C076BV1EZ19"
      }
    },
    {
      name     = "news_bot"
      trigger  = "cron"
      schedule = "cron(15 15 ? * MON-FRI *)" # 10:15am EST
      env_vars = {
        NEWS_BOT_TOKEN    = data.sops_file.common.data.news_bot_token
        SLACK_CHANNEL_ID  = "CADHSJ25V"
      }
    },
    {
      name     = "nist_vuln_alerts"
      trigger  = "cron"
      schedule = "cron(15 15 ? * MON-FRI *)" # 10:15am EST
      env_vars = {
        NEWS_BOT_TOKEN    = data.sops_file.common.data.news_bot_token
        NVD_API_TOKEN     = data.sops_file.common.data.nvd_api_token
        SLACK_CHANNEL_ID  = "C02PKTWA60Z"
      }
    },
    {
      name     = "devision"
      trigger  = "cron"
      schedule = "cron(15 15 ? * MON-FRI *)"
      env_vars = {
        DD_API_KEY            = data.sops_file.common.data.dd_signal_api_key
        DD_APP_KEY            = data.sops_file.common.data.dd_signal_app_key
        DD_SITE               = "datadoghq.com"
        KANDJI_API_KEY        = data.sops_file.common.data.kandji_api_key
        KANDJI_SUBDOMAIN      = "apprenticefs"
        DATA_BUCKET           = local.data_bucket
        CROWDSTRIKE_API_KEY   = data.sops_file.common.data.crowdstrike_api_secret
        CROWDSTRIKE_CLIENT_ID = data.sops_file.common.data.crowdstrike_api_client_id
        REFTAB_SECRET_KEY     = data.sops_file.common.data.reftab_secret
        REFTAB_PUBLIC_KEY     = data.sops_file.common.data.reftab_publickey
        CLOUDFLARE_API_KEY    = data.sops_file.common.data.cloudflare_api_key
      }
    },
    {
      name     = "env_config"
      trigger  = "cron"
      schedule = "cron(15 15 ? * MON-FRI *)" # 10:15am EST
      env_vars = {
        GITHUB_TOKEN     = data.sops_file.common.data.github_token
        REPO_OWNER       = "ApprenticeFS"
        REPO_NAME        = "afs_config"
        DATA_BUCKET      = local.data_bucket
        OPENAI_API_KEY   = data.sops_file.common.data.openai_api_key
      }
    },
    {
      name     = "ghas"
      trigger  = "cron"
      schedule = "cron(15 15 ? * MON-FRI *)" # 10:15am EST
      env_vars = {
        GITHUB_TOKEN     = data.sops_file.common.data.github_token
        REPO_OWNER       = "ApprenticeFS"
        REPO_NAME        = "monorepo"
        DATA_BUCKET      = local.data_bucket
        OPENAI_API_KEY   = data.sops_file.common.data.openai_api_key
      }
    },
    {
      name     = "cs_iom"
      trigger  = "cron"
      schedule = "cron(15 15 ? * MON-FRI *)" # 10:15am EST
      env_vars = {
        CROWDSTRIKE_API_SECRET   = data.sops_file.common.data.crowdstrike_api_secret
        CROWDSTRIKE_API_CLIENT_ID = data.sops_file.common.data.crowdstrike_api_client_id
        DATA_BUCKET              = local.data_bucket
      }
    },
    {
      name     = "ask_fangorn"
      trigger  = "sns"
      env_vars = {
        ANTHROPIC_API_KEY = data.sops_file.common.data.anthropic_api_key
        OPENAI_API_KEY    = data.sops_file.common.data.openai_api_key
      } 
    }
  ]
  func_defaults = {
    env_vars    = {
      NEWS_BOT_TOKEN = data.sops_file.common.data.news_bot_token
    }
    arch        = ["x86_64"]
    trigger     = "sns"
    filename    = "lambda.zip"
    buckets     = []
    db          = false
  }
  functions = {
    for func in local.func_blocks : func.name => merge(local.func_defaults, func)
  }
  outputs_map = { for function in local.functions : function.name => module.lambda[function.name] }
}
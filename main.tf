data "terraform_remote_state" "env_region" {
  backend = "s3"
  config = {
    bucket = "afs-infra-tf-state"
    key    = "env:/${local.env_config.cluster_region}/terraform.tfstate"
    region = "us-east-1"
  }
}

data "terraform_remote_state" "oracle" {
  backend = "s3"
  config = {
    bucket = "afs-infra-tf-state"
    key    = "env:/${local.env_config.cluster_region}/afs-oracle.tfstate"
    region = "us-east-1"
  }
}

data "sops_file" "common" {
  source_file = "secrets/common.enc.yaml"
}

locals {
  monitor_defaults = {
    type    = "log_detection"
    enabled = true
    evaluation_window   = 300    # 5 minutes
    keep_alive         = 3600    # 1 hour 
    max_signal_duration = 86400  # 24 hours
    detection_method    = "threshold"
    decrease_criticality_based_on_env = false
    has_extended_title = false
    tags = [
      "service:tempo",
      "type:security",
      "managed-by:terraform"
    ]
  }

  # Default alert format for monitors that don't have custom messages
  alert_format = <<-EOT
    - **Service:** `{{service}}`
    - **Path:** `{{http.url_details.path}}`
    - **Host:** `{{http.url_details.host}}`
    - **IP Address:** `{{network.client.geoip.ipAddress}}`
    - **Location:** `{{network.client.geoip.city.name}}, {{network.client.geoip.country.name}}`
    - **Environment:** `{{dd.env}}`
    
    [View Playbook](https://github.com/ApprenticeFS/afs-sec/tree/main/lucius/playbooks)
  EOT

  # Original custom messages preserved exactly
  custom_messages = {
    session_hijacking = <<-EOT
      {{#is_alert}}
      :warning: Session Hijacking Detected :warning:
      
      - IP Address: {{log.attributes.network.client.geoip.ipAddress}}
      - Number of Active Sessions: {{value}}
      - Recent Session IDs: {{log.attributes.user.session_id_client_trace}}
      - User Agents: {{log.attributes.http.headers.user-agent}}
      - Service: {{log.attributes.http.url_details.host}}
      - Environment: {{log.attributes.dd.env}}
      - Timestamp: {{log.attributes.timestamp}}
      
      \@webhook-Lucius_Session_Hijacking 
      \@workflow-Jeffrey-Jun-01-2024-0338 
      \@slack-sec-alerts-development
      
      {{/is_alert}}
    EOT

    impossible_travel = <<-EOT
      {{#is_alert}}
      :warning: Impossible Travel Detected :warning:
      
      - Session ID: {{log.attributes.user.session_id_client_trace}}
      - Origin Location: {{log.attributes.user.geoip.city.name}}, {{log.attributes.user.geoip.country.name}}
      - Recent Location: {{log.attributes.user.geoip.city.name}}, {{log.attributes.user.geoip.country.name}}
      - IP Address: {{log.attributes.user.geoip.ipAddress}}
      - Device Info: {{log.attributes.http.headers.user-agent}}
      - Service: {{log.attributes.http.url_details.host}}
      - Environment: {{log.attributes.dd.env}}
      - Timestamp: {{log.attributes.timestamp}}
      
      \@webhook-Lucius_Impossible_Travel 
      \@workflow-Jeffrey-Jun-01-2024-0338 
      \@slack-sec-alerts-development
      
      {{/is_alert}}
    EOT

    mass_enumeration = <<-EOT
      {{#is_alert}}
      :warning: Mass Enumeration Detected :warning:
      
      - Number of enumeration attempts: {{value}}
      - User Email: {{log.attributes.http.headers.cookie.ssoOriginatingUser}}
      - IP Address: {{log.attributes.network.client.geoip.ipAddress}}
      - Location: {{log.attributes.network.client.geoip.city.name}}, {{log.attributes.network.client.geoip.country.name}}
      - Device Info: {{log.attributes.http.headers.user-agent}}
      - Service: {{log.attributes.http.url_details.host}}
      - Environment: {{log.attributes.dd.env}}
      - Timestamp: {{log.attributes.timestamp}}
      
      \@webhook-Lucius_Enumeration_Alert 
      \@slack-sec-alerts-development
      
      {{/is_alert}}
    EOT

    privilege_escalation = <<-EOT
      {{#is_alert}}
      :warning: Privilege Escalation Attempt Detected :warning:
      
      - Number of attempts: {{value}}
      - IP Address: {{log.attributes.network.client.geoip.ipAddress}}
      - Location: {{log.attributes.network.client.geoip.city.name}}, {{log.attributes.network.client.geoip.country.name}}
      - Device Info: {{log.attributes.http.headers.user-agent}}
      - Error Message: {{log.attributes.log.error}}
      - Service: {{log.attributes.http.url_details.host}}
      - Environment: {{log.attributes.dd.env}}
      - Timestamp: {{log.attributes.timestamp}}
      
      \@webhook-Lucius_Privilege_Escalation 
      \@workflow-Jeffrey-Jun-01-2024-0338 
      \@slack-sec-alerts-development
      
      {{/is_alert}}
    EOT
    
    exfiltration = <<-EOT
      {{#is_alert}}
      :warning: Data Exfiltration Detected :warning:
      
      - Number of Downloads: {{value}}
      - IP Address: {{log.attributes.network.client.geoip.ipAddress}}
      - User Email: {{log.attributes.http.headers.cookie.ssoOriginatingUser}}
      - Endpoint Accessed: {{log.attributes.http.url_details.path}}
      - Host: {{log.attributes.http.url_details.host}}
      - Timestamp: {{log.attributes.timestamp}}
      
      \@webhook-Lucius_Data_Exfiltration_Alert 
      \@slack-sec-alerts-development
      
      {{/is_alert}}
    EOT
  }

  notifications = {
    session = [
      "@webhook-Lucius_Session_Hijacking",
      "@workflow-Jeffrey-Jun-01-2024-0338",
      "@slack-sec-alerts-development"
    ],
    impossible_travel = [
      "@webhook-Lucius_Impossible_Travel",
      "@workflow-Jeffrey-Jun-01-2024-0338", 
      "@slack-sec-alerts-development"
    ],
    privilege_escalation = [
      "@webhook-Lucius_Privilege_Escalation",
      "@workflow-Jeffrey-Jun-01-2024-0338",
      "@slack-sec-alerts-development"
    ],
    exfiltration = [
      "@webhook-Lucius_Data_Exfiltration_Alert",
      "@slack-sec-alerts-development"
    ],
    enumeration = [
      "@webhook-Lucius_Enumeration_Alert",
      "@slack-sec-alerts-development" 
    ],
    none = []
  }
}

# Main resource that builds monitors from all the groups
resource "datadog_security_monitoring_rule" "monitors" {
  for_each = merge(
    local.auth_monitors,
    local.privilege_monitors,
    local.data_monitors,
    local.network_monitors,
    local.security_monitors
  )

  name               = "afs-sec-${each.value.name}"
  enabled            = lookup(each.value, "enabled", true)
  type               = "log_detection"
  has_extended_title = false
  message            = lookup(local.custom_messages, each.key, local.alert_format)

  dynamic "query" {
    for_each = each.value.queries
    content {
      name            = query.value.name
      query           = query.value.query
      aggregation     = lookup(query.value, "aggregation", "count")
      group_by_fields = lookup(query.value, "group_by_fields", [])
      distinct_fields = []
      metrics         = []
    }
  }

  case {
    status        = lookup(each.value.cases[0], "status", "medium")
    condition     = each.value.cases[0].condition 
    notifications = lookup(each.value.cases[0], "notifications", local.notifications.none)
    name          = lookup(each.value.cases[0], "name", null)
  }

  options {
    evaluation_window   = lookup(each.value.options, "evaluation_window", local.monitor_defaults.evaluation_window)
    keep_alive         = lookup(each.value.options, "keep_alive", local.monitor_defaults.keep_alive)
    max_signal_duration = lookup(each.value.options, "max_signal_duration", local.monitor_defaults.max_signal_duration)
    detection_method    = lookup(each.value.options, "detection_method", local.monitor_defaults.detection_method)
    decrease_criticality_based_on_env = false
  }

  tags = distinct(concat(local.monitor_defaults.tags, lookup(each.value, "tags", [])))
}

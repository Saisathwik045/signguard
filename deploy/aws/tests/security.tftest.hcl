mock_provider "aws" {}
variables {
  account_id       = "123456789012"
  ami_id           = "ami-0123456789abcdef0"
  instance_profile = "signguard-staging-runtime"
}
run "default_is_no_resources" {
  command = plan
  assert {
    condition     = length(aws_instance.staging) == 0 && length(aws_s3_bucket.audit) == 0 && length(aws_ecr_repository.images) == 0
    error_message = "No resource may be planned without explicit spending authorization."
  }
}
run "approved_still_has_no_ingress" {
  command = plan
  variables { spending_authorized = true }
  assert {
    condition     = length(aws_vpc_security_group_ingress_rule.maintenance) == 0
    error_message = "Spending approval does not approve external ingress."
  }
  assert {
    condition     = aws_instance.staging[0].metadata_options[0].http_tokens == "required" && aws_instance.staging[0].metadata_options[0].http_put_response_hop_limit == 1
    error_message = "Container metadata credential protection must remain enabled."
  }
  assert {
    condition     = aws_instance.staging[0].root_block_device[0].encrypted && aws_ebs_volume.audit[0].encrypted && aws_instance.staging[0].credit_specification[0].cpu_credits == "standard"
    error_message = "Encrypted disks and no unlimited CPU-credit billing are mandatory."
  }
}

run "maintenance_exposes_only_ca_and_authenticated_https" {
  command = plan
  variables {
    spending_authorized   = true
    allow_private_ingress = true
  }
  assert {
    condition     = length(aws_vpc_security_group_ingress_rule.maintenance) == 2 && aws_vpc_security_group_ingress_rule.maintenance[0].from_port == 80 && aws_vpc_security_group_ingress_rule.maintenance[1].from_port == 443
    error_message = "Maintenance must never expose SSH, controller or raw Streamlit ports."
  }
}

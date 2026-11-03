terraform {
  required_version = "~> 1.16.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.20.0" }
  }
  backend "s3" {}
}
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  default_tags { tags = { Project = "signguard", Environment = "staging" } }
}
variable "account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "An explicit authorized AWS account is required."
  }
}
variable "region" { default = "us-east-1" }
variable "spending_authorized" {
  type    = bool
  default = false
}
variable "allow_private_ingress" {
  type    = bool
  default = false
}
variable "instance_profile" { type = string }
variable "ami_id" {
  type = string
  validation {
    condition     = can(regex("^ami-[0-9a-f]+$", var.ami_id))
    error_message = "Pin a reviewed Canonical Ubuntu 24.04 x86_64 AMI; never use an unreviewed latest image."
  }
}
locals { enabled = var.spending_authorized ? 1 : 0 }
resource "aws_vpc" "staging" {
  count                = local.enabled
  cidr_block           = "10.87.0.0/24"
  enable_dns_hostnames = true
  enable_dns_support   = true
}
resource "aws_subnet" "staging" {
  count      = local.enabled
  vpc_id     = aws_vpc.staging[0].id
  cidr_block = "10.87.0.0/26"
}
resource "aws_internet_gateway" "staging" {
  count  = local.enabled
  vpc_id = aws_vpc.staging[0].id
}
resource "aws_route_table" "staging" {
  count  = local.enabled
  vpc_id = aws_vpc.staging[0].id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.staging[0].id
  }
}
resource "aws_route_table_association" "staging" {
  count          = local.enabled
  subnet_id      = aws_subnet.staging[0].id
  route_table_id = aws_route_table.staging[0].id
}
resource "aws_security_group" "staging" {
  count       = local.enabled
  name_prefix = "signguard-staging-"
  description = "No SSH/controller/Streamlit ingress. HTTPS maintenance only after separate review."
  vpc_id      = aws_vpc.staging[0].id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Host bootstrap, registry, OAuth, SSM and CA egress; PDF worker network is none."
  }
  ingress = []
}
resource "aws_vpc_security_group_ingress_rule" "maintenance" {
  count             = var.spending_authorized && var.allow_private_ingress ? 2 : 0
  security_group_id = aws_security_group.staging[0].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = [80, 443][count.index]
  to_port           = [80, 443][count.index]
  description       = "Reviewed ACME challenge or authenticated HTTPS maintenance; uploads remain disabled."
}

resource "aws_instance" "staging" {
  count                       = local.enabled
  ami                         = var.ami_id
  instance_type               = "t3a.medium"
  subnet_id                   = aws_subnet.staging[0].id
  vpc_security_group_ids      = [aws_security_group.staging[0].id]
  associate_public_ip_address = true
  iam_instance_profile        = var.instance_profile
  user_data                   = file("${path.module}/host/bootstrap.sh")
  user_data_replace_on_change = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }
  credit_specification { cpu_credits = "standard" }
  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 80
  }
  tags = { Name = "signguard-staging", ManagedBy = "signguard-deployment" }
}
resource "aws_eip" "staging" {
  count    = local.enabled
  instance = aws_instance.staging[0].id
  domain   = "vpc"
}
resource "aws_ebs_volume" "audit" {
  count             = local.enabled
  availability_zone = aws_instance.staging[0].availability_zone
  size              = 20
  type              = "gp3"
  encrypted         = true
  tags              = { Name = "signguard-staging-audit" }
  lifecycle { prevent_destroy = true }
}
resource "aws_volume_attachment" "audit" {
  count       = local.enabled
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.audit[0].id
  instance_id = aws_instance.staging[0].id
}
resource "aws_s3_bucket" "audit" {
  count               = local.enabled
  bucket              = "signguard-staging-audit-${var.account_id}"
  object_lock_enabled = true
  force_destroy       = false
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_public_access_block" "audit" {
  count                   = local.enabled
  bucket                  = aws_s3_bucket.audit[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "audit" {
  count  = local.enabled
  bucket = aws_s3_bucket.audit[0].id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  count  = local.enabled
  bucket = aws_s3_bucket.audit[0].id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_object_lock_configuration" "audit" {
  count      = local.enabled
  bucket     = aws_s3_bucket.audit[0].id
  depends_on = [aws_s3_bucket_versioning.audit]
  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = 7
    }
  }
}
resource "aws_s3_bucket_policy" "audit" {
  count  = local.enabled
  bucket = aws_s3_bucket.audit[0].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Deny", Principal = "*", Action = "s3:*",
    Resource  = [aws_s3_bucket.audit[0].arn, "${aws_s3_bucket.audit[0].arn}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
resource "aws_secretsmanager_secret" "runtime" {
  count                   = local.enabled
  name                    = "signguard/staging/runtime"
  recovery_window_in_days = 30
  description             = "Browser-entered OAuth settings; no secret values in Terraform/state or Git."
}
resource "aws_ecr_repository" "images" {
  for_each             = var.spending_authorized ? toset(["worker", "ui", "controller"]) : toset([])
  name                 = "signguard-staging-${each.key}"
  image_tag_mutability = "IMMUTABLE"
  encryption_configuration { encryption_type = "AES256" }
  image_scanning_configuration { scan_on_push = true }
}
output "instance_id" { value = try(aws_instance.staging[0].id, null) }
output "prospective_https_origin" {
  value       = try("https://${aws_eip.staging[0].public_ip}", null)
  description = "Prospective only: no claim of TLS, login, worker or deployment verification."
}
output "audit_volume_id" { value = try(aws_ebs_volume.audit[0].id, null) }

resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  count      = local.enabled
  bucket     = aws_s3_bucket.audit[0].id
  depends_on = [aws_s3_bucket_versioning.audit]
  rule {
    id     = "bounded-audit-retention"
    status = "Enabled"
    filter { prefix = "anchors/" }
    expiration { days = 30 }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

<#
.SYNOPSIS
  Provision the full AWS infrastructure for LibraryConnekto from Windows
  PowerShell. Mirrors AWS_Deploy.md Sections 2-5 and 10-13 in one script.

.DESCRIPTION
  Idempotent: re-running re-uses existing resources where it can.
  Outputs an "aws-state.json" with all IDs you'll need later.

  Prerequisites:
    - AWS CLI v2 installed and `aws configure` already run.
    - An IAM user with AdministratorAccess (only for first-time setup).
    - You own the domain you pass via -Domain (Route 53 will be created
      and the registrar's NS records must be updated to AWS nameservers).

.PARAMETER Region
  AWS region. Default ap-south-1 (Mumbai).
.PARAMETER Domain
  Apex domain you own, e.g. libraryconnekto.me
.PARAMETER ApiSubdomain
  Subdomain for backend API. Default api.<domain>.
.PARAMETER DbPassword
  Master password for RDS (>= 12 chars, no '@', '/', '"').
  Pass it as a SecureString, e.g.:
    $secure = Read-Host "DB password" -AsSecureString
    .\01-provision-aws.ps1 -Domain ... -DbPassword $secure
.PARAMETER InstanceType
  EC2 instance type. Default t3.micro (Free Tier friendly).
.PARAMETER BucketName
  S3 bucket for the frontend. Must be globally unique.

.EXAMPLE
  .\01-provision-aws.ps1 -Domain libraryconnekto.me -DbPassword 'StrongP@ss-Removed'
#>
[CmdletBinding()]
param(
  [string]$Region = "ap-south-1",
  [Parameter(Mandatory)] [string]$Domain,
  [string]$ApiSubdomain,
  [Parameter(Mandatory)] [securestring]$DbPassword,
  [string]$InstanceType = "t3.micro",
  [string]$KeyName = "libraryconnekto-key",
  [string]$SgName = "libraryconnekto-sg",
  [string]$RdsSgName = "libraryconnekto-rds-sg",
  [string]$DbInstanceId = "libraryconnekto-db",
  [string]$DbName = "libraryconnekto",
  [string]$DbUsername = "lcadmin",
  [string]$BucketName = "libraryconnekto-frontend",
  [string]$StateFile = "aws-state.json"
)

$ErrorActionPreference = "Stop"

if (-not $ApiSubdomain) { $ApiSubdomain = "api.$Domain" }

# Decode the SecureString once for use in AWS CLI calls. The plain value is
# kept inside this script's process memory only; it is never written to disk
# (the rendered .env is created and SCP'd by the runbook, not by this script).
$DbPasswordPlain = [System.Net.NetworkCredential]::new("", $DbPassword).Password

function Invoke-Aws {
  param([Parameter(Mandatory)][string[]]$AwsArgs, [switch]$AllowFail)
  $output = & aws @AwsArgs 2>&1
  if ($LASTEXITCODE -ne 0 -and -not $AllowFail) {
    Write-Error "aws $($AwsArgs -join ' ') failed:`n$output"
  }
  return ($output -join "`n")
}

function Save-State($state) {
  $state | ConvertTo-Json -Depth 6 | Set-Content -Path $StateFile -Encoding UTF8
  Write-Host "  state -> $StateFile" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------
Write-Host "== LibraryConnekto AWS provisioning ==" -ForegroundColor Cyan
Write-Host "Region:        $Region"
Write-Host "Domain:        $Domain"
Write-Host "API subdomain: $ApiSubdomain"
Write-Host "Bucket:        $BucketName"

$state = @{}
if (Test-Path $StateFile) {
  $state = Get-Content $StateFile -Raw | ConvertFrom-Json -AsHashtable
  Write-Host "Loaded existing state from $StateFile" -ForegroundColor Yellow
}

# ---- 0. Sanity check --------------------------------------------------
Write-Host "`n[0/10] Verifying AWS credentials"
$identity = Invoke-Aws -AwsArgs @("sts","get-caller-identity","--region",$Region) | ConvertFrom-Json
$state.account_id = $identity.Account
Write-Host "  account: $($identity.Account) ($($identity.Arn))"

# ---- 1. Latest Ubuntu 22.04 AMI --------------------------------------
Write-Host "`n[1/10] Resolving latest Ubuntu 22.04 AMI"
$amiId = (Invoke-Aws -AwsArgs @(
  "ec2","describe-images",
  "--owners","099720109477",
  "--filters","Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*","Name=state,Values=available",
  "--query","sort_by(Images, &CreationDate)[-1].ImageId",
  "--output","text",
  "--region",$Region
)).Trim()
$state.ami_id = $amiId
Write-Host "  AMI: $amiId"

# ---- 2. Key pair ------------------------------------------------------
Write-Host "`n[2/10] Ensuring key pair $KeyName"
$keyExists = $false
try { Invoke-Aws -AwsArgs @("ec2","describe-key-pairs","--key-names",$KeyName,"--region",$Region) | Out-Null; $keyExists = $true } catch {}
if (-not $keyExists) {
  $keyMaterial = Invoke-Aws -AwsArgs @(
    "ec2","create-key-pair","--key-name",$KeyName,
    "--query","KeyMaterial","--output","text","--region",$Region
  )
  $pemPath = Join-Path -Path (Get-Location) -ChildPath "$KeyName.pem"
  $keyMaterial | Set-Content -Path $pemPath -Encoding ASCII
  icacls $pemPath /inheritance:r | Out-Null
  icacls $pemPath /grant:r "$($env:USERNAME):(R)" | Out-Null
  Write-Host "  saved -> $pemPath" -ForegroundColor Green
  $state.key_pem_path = $pemPath
} else {
  Write-Host "  reusing existing key pair (PEM must already be on disk)" -ForegroundColor Yellow
}
$state.key_name = $KeyName
Save-State $state

# ---- 3. EC2 security group ------------------------------------------
Write-Host "`n[3/10] Ensuring EC2 security group $SgName"
$sgId = $state.sg_id
if (-not $sgId) {
  try {
    $sgId = (Invoke-Aws -AwsArgs @("ec2","describe-security-groups","--group-names",$SgName,"--region",$Region,"--query","SecurityGroups[0].GroupId","--output","text") -as [string]).Trim()
  } catch {}
}
if (-not $sgId -or $sgId -eq "None") {
  $sgId = (Invoke-Aws -AwsArgs @("ec2","create-security-group","--group-name",$SgName,"--description","LibraryConnekto EC2 SG","--region",$Region,"--query","GroupId","--output","text")).Trim()
  Write-Host "  created $sgId" -ForegroundColor Green
} else { Write-Host "  reusing $sgId" }
$state.sg_id = $sgId

$myIp = (Invoke-WebRequest -UseBasicParsing https://checkip.amazonaws.com).Content.Trim()
$rules = @(
  @("22","$myIp/32"),
  @("80","0.0.0.0/0"),
  @("443","0.0.0.0/0")
)
foreach ($rule in $rules) {
  Invoke-Aws -AllowFail -AwsArgs @(
    "ec2","authorize-security-group-ingress",
    "--group-id",$sgId,"--protocol","tcp",
    "--port",$rule[0],"--cidr",$rule[1],"--region",$Region
  ) | Out-Null
}
Save-State $state

# ---- 4. Default VPC + subnets for RDS -------------------------------
Write-Host "`n[4/10] Resolving default VPC & subnets"
$vpcId = (Invoke-Aws -AwsArgs @("ec2","describe-vpcs","--filters","Name=isDefault,Values=true","--query","Vpcs[0].VpcId","--output","text","--region",$Region)).Trim()
$state.vpc_id = $vpcId
$subnetIds = (Invoke-Aws -AwsArgs @("ec2","describe-subnets","--filters","Name=vpc-id,Values=$vpcId","--query","Subnets[*].SubnetId","--output","text","--region",$Region)).Trim() -split "\s+"
$state.subnet_ids = $subnetIds
Write-Host "  VPC $vpcId / subnets $($subnetIds -join ', ')"

# ---- 5. RDS subnet group + security group ---------------------------
Write-Host "`n[5/10] Ensuring RDS subnet group + SG"
$subnetGroupArgs = @(
  "rds","create-db-subnet-group",
  "--db-subnet-group-name","libraryconnekto-db-subnet",
  "--db-subnet-group-description","LibraryConnekto RDS subnets",
  "--subnet-ids"
) + $subnetIds + @("--region",$Region)
Invoke-Aws -AllowFail -AwsArgs $subnetGroupArgs | Out-Null

$rdsSgId = $state.rds_sg_id
if (-not $rdsSgId) {
  try {
    $rdsSgId = (Invoke-Aws -AwsArgs @("ec2","describe-security-groups","--filters","Name=group-name,Values=$RdsSgName","Name=vpc-id,Values=$vpcId","--query","SecurityGroups[0].GroupId","--output","text","--region",$Region) -as [string]).Trim()
  } catch {}
}
if (-not $rdsSgId -or $rdsSgId -eq "None") {
  $rdsSgId = (Invoke-Aws -AwsArgs @("ec2","create-security-group","--group-name",$RdsSgName,"--description","LibraryConnekto RDS SG","--vpc-id",$vpcId,"--region",$Region,"--query","GroupId","--output","text")).Trim()
}
Invoke-Aws -AllowFail -AwsArgs @(
  "ec2","authorize-security-group-ingress",
  "--group-id",$rdsSgId,"--protocol","tcp","--port","5432",
  "--source-group",$sgId,"--region",$Region
) | Out-Null
$state.rds_sg_id = $rdsSgId
Save-State $state

# ---- 6. Create RDS instance ------------------------------------------
Write-Host "`n[6/10] Ensuring RDS instance $DbInstanceId"
$rdsExists = $false
try { Invoke-Aws -AwsArgs @("rds","describe-db-instances","--db-instance-identifier",$DbInstanceId,"--region",$Region) | Out-Null; $rdsExists = $true } catch {}
if (-not $rdsExists) {
  Invoke-Aws -AwsArgs @(
    "rds","create-db-instance",
    "--db-instance-identifier",$DbInstanceId,
    "--db-instance-class","db.t3.micro",
    "--engine","postgres","--engine-version","15.4",
    "--master-username",$DbUsername,"--master-user-password",$DbPasswordPlain,
    "--db-name",$DbName,"--allocated-storage","20","--storage-type","gp2",
    "--no-multi-az","--no-publicly-accessible",
    "--vpc-security-group-ids",$rdsSgId,
    "--db-subnet-group-name","libraryconnekto-db-subnet",
    "--backup-retention-period","7","--region",$Region
  ) | Out-Null
  Write-Host "  Waiting for RDS to become available (5-10 min)..." -ForegroundColor Yellow
  Invoke-Aws -AwsArgs @("rds","wait","db-instance-available","--db-instance-identifier",$DbInstanceId,"--region",$Region) | Out-Null
}
$rdsEndpoint = (Invoke-Aws -AwsArgs @("rds","describe-db-instances","--db-instance-identifier",$DbInstanceId,"--query","DBInstances[0].Endpoint.Address","--output","text","--region",$Region)).Trim()
$state.rds_endpoint = $rdsEndpoint
$state.database_url = "postgresql://${DbUsername}:<DB_PASSWORD>@${rdsEndpoint}:5432/${DbName}"
Save-State $state
Write-Host "  RDS endpoint: $rdsEndpoint"

# ---- 7. EC2 instance + Elastic IP ------------------------------------
Write-Host "`n[7/10] Ensuring EC2 instance & Elastic IP"
$instanceId = $state.instance_id
if (-not $instanceId) {
  $tagSpec = "ResourceType=instance,Tags=[{Key=Name,Value=libraryconnekto-backend}]"
  $bdm = '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":20,"VolumeType":"gp3","DeleteOnTermination":true}}]'
  $instanceId = (Invoke-Aws -AwsArgs @(
    "ec2","run-instances",
    "--image-id",$amiId,"--instance-type",$InstanceType,
    "--key-name",$KeyName,"--security-group-ids",$sgId,
    "--block-device-mappings",$bdm,
    "--tag-specifications",$tagSpec,
    "--region",$Region,
    "--query","Instances[0].InstanceId","--output","text"
  )).Trim()
  Invoke-Aws -AwsArgs @("ec2","wait","instance-running","--instance-ids",$instanceId,"--region",$Region) | Out-Null
}
$state.instance_id = $instanceId

$eipAlloc = $state.eip_alloc_id
if (-not $eipAlloc) {
  $eipAlloc = (Invoke-Aws -AwsArgs @("ec2","allocate-address","--domain","vpc","--region",$Region,"--query","AllocationId","--output","text")).Trim()
  Invoke-Aws -AwsArgs @("ec2","associate-address","--instance-id",$instanceId,"--allocation-id",$eipAlloc,"--region",$Region) | Out-Null
}
$state.eip_alloc_id = $eipAlloc
$serverIp = (Invoke-Aws -AwsArgs @("ec2","describe-addresses","--allocation-ids",$eipAlloc,"--query","Addresses[0].PublicIp","--output","text","--region",$Region)).Trim()
$state.server_ip = $serverIp
Save-State $state
Write-Host "  EC2 $instanceId -> $serverIp"

# ---- 8. S3 bucket for frontend ---------------------------------------
Write-Host "`n[8/10] Ensuring S3 bucket $BucketName"
$bucketExists = $false
try { Invoke-Aws -AwsArgs @("s3api","head-bucket","--bucket",$BucketName,"--region",$Region) | Out-Null; $bucketExists = $true } catch {}
if (-not $bucketExists) {
  Invoke-Aws -AwsArgs @(
    "s3api","create-bucket","--bucket",$BucketName,"--region",$Region,
    "--create-bucket-configuration","LocationConstraint=$Region"
  ) | Out-Null
}
Invoke-Aws -AllowFail -AwsArgs @("s3api","delete-public-access-block","--bucket",$BucketName) | Out-Null
$website = '{"IndexDocument":{"Suffix":"index.html"},"ErrorDocument":{"Key":"index.html"}}'
Invoke-Aws -AwsArgs @("s3api","put-bucket-website","--bucket",$BucketName,"--website-configuration",$website) | Out-Null
$policy = @"
{"Version":"2012-10-17","Statement":[{"Sid":"PublicReadGetObject","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::$BucketName/*"}]}
"@
Invoke-Aws -AwsArgs @("s3api","put-bucket-policy","--bucket",$BucketName,"--policy",$policy) | Out-Null
$state.bucket_name = $BucketName
$state.bucket_website = "$BucketName.s3-website.$Region.amazonaws.com"
Save-State $state

# ---- 9. CloudFront distribution --------------------------------------
Write-Host "`n[9/10] Ensuring CloudFront distribution"
$cfId = $state.cloudfront_id
if (-not $cfId) {
  $caller = "libraryconnekto-" + [int][double]::Parse((Get-Date -UFormat %s))
  $cfConfig = @"
{
  "CallerReference": "$caller",
  "Comment": "LibraryConnekto Frontend CDN",
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-$BucketName",
    "ViewerProtocolPolicy": "redirect-to-https",
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "AllowedMethods": { "Quantity": 2, "Items": ["GET","HEAD"] }
  },
  "Origins": {
    "Quantity": 1,
    "Items": [{
      "Id": "S3-$BucketName",
      "DomainName": "$($state.bucket_website)",
      "CustomOriginConfig": {
        "HTTPPort": 80, "HTTPSPort": 443,
        "OriginProtocolPolicy": "http-only",
        "OriginSslProtocols": { "Quantity": 1, "Items": ["TLSv1.2"] },
        "OriginReadTimeout": 30, "OriginKeepaliveTimeout": 5
      }
    }]
  },
  "CustomErrorResponses": {
    "Quantity": 2,
    "Items": [
      {"ErrorCode":404,"ResponsePagePath":"/index.html","ResponseCode":"200","ErrorCachingMinTTL":0},
      {"ErrorCode":403,"ResponsePagePath":"/index.html","ResponseCode":"200","ErrorCachingMinTTL":0}
    ]
  },
  "Enabled": true,
  "PriceClass": "PriceClass_200"
}
"@
  $cfFile = New-TemporaryFile
  $cfConfig | Set-Content $cfFile -Encoding UTF8
  $cfOut = Invoke-Aws -AwsArgs @("cloudfront","create-distribution","--distribution-config","file://$cfFile","--region","us-east-1")
  Remove-Item $cfFile -Force
  $cfJson = $cfOut | ConvertFrom-Json
  $cfId = $cfJson.Distribution.Id
  $state.cloudfront_domain = $cfJson.Distribution.DomainName
}
$state.cloudfront_id = $cfId
Save-State $state
Write-Host "  CloudFront $cfId -> $($state.cloudfront_domain)"

# ---- 10. Route 53 hosted zone + records ------------------------------
Write-Host "`n[10/10] Ensuring Route 53 hosted zone for $Domain"
$hostedZones = Invoke-Aws -AwsArgs @("route53","list-hosted-zones-by-name","--dns-name",$Domain,"--max-items","1") | ConvertFrom-Json
$zoneId = $null
if ($hostedZones.HostedZones.Count -gt 0 -and $hostedZones.HostedZones[0].Name -eq "$Domain.") {
  $zoneId = $hostedZones.HostedZones[0].Id -replace "/hostedzone/",""
} else {
  $caller = "libraryconnekto-zone-" + [int][double]::Parse((Get-Date -UFormat %s))
  $zoneOut = Invoke-Aws -AwsArgs @("route53","create-hosted-zone","--name",$Domain,"--caller-reference",$caller) | ConvertFrom-Json
  $zoneId = $zoneOut.HostedZone.Id -replace "/hostedzone/",""
}
$state.hosted_zone_id = $zoneId

$change = @"
{
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$Domain",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z2FDTNDATAQYW2",
          "DNSName": "$($state.cloudfront_domain)",
          "EvaluateTargetHealth": false
        }
      }
    },
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$ApiSubdomain",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [{"Value": "$serverIp"}]
      }
    }
  ]
}
"@
$changeFile = New-TemporaryFile
$change | Set-Content $changeFile -Encoding UTF8
Invoke-Aws -AwsArgs @("route53","change-resource-record-sets","--hosted-zone-id",$zoneId,"--change-batch","file://$changeFile") | Out-Null
Remove-Item $changeFile -Force

$ns = (Invoke-Aws -AwsArgs @("route53","get-hosted-zone","--id",$zoneId,"--query","DelegationSet.NameServers","--output","text")).Trim() -split "\s+"
$state.route53_nameservers = $ns
Save-State $state

Write-Host "`n=========== SUMMARY ===========" -ForegroundColor Cyan
Write-Host "EC2 IP (api):       $serverIp"
Write-Host "RDS endpoint:       $rdsEndpoint"
Write-Host "S3 bucket:          $BucketName"
Write-Host "CloudFront ID:      $cfId"
Write-Host "CloudFront domain:  $($state.cloudfront_domain)"
Write-Host "Hosted zone ID:     $zoneId"
Write-Host "Nameservers:"
$ns | ForEach-Object { Write-Host "  - $_" }
Write-Host
Write-Host "Next steps:"
Write-Host " 1. Update your registrar to point NS records to the above nameservers."
Write-Host " 2. Fill in /home/ubuntu/backend/.env from .env.aws.example using the values in $StateFile."
Write-Host " 3. SCP the .env then run deploy/aws/scripts/ec2-bootstrap.sh on the instance."
Write-Host " 4. After DNS resolves, request the SSL cert via certbot (see ec2-bootstrap output)."
Write-Host " 5. Build and sync the frontend: see deploy/aws/scripts/02-build-and-deploy-frontend.ps1"


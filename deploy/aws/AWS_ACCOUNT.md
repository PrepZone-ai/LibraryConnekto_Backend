# LibraryConnekto — AWS account reference

Use this file when filling ARNs, IAM policies, or verifying `aws sts get-caller-identity`.

| Field | Value |
| --- | --- |
| **Account display name** | libraryconnekto |
| **Account ID** | `836809166355` |
| **Billing entity** | Amazon Web Services India Private Limited |
| **Default deployment region** | `ap-south-1` (Asia Pacific — Mumbai) |
| **IAM console user** | `sandeep-admin` |
| **Console sign-in URL** | `https://836809166355.signin.aws.amazon.com/console` |

## Console vs CLI (important)

- **`sandeep-admin`** is an **IAM user** for the **web console** (browser). You sign in with the **password** you set (keep it private; never commit it or paste it in code).
- **PowerShell / `01-provision-aws.ps1` / `aws` commands** do **not** use that password. They use **Access keys** (Access Key ID + Secret Access Key).

### Set up CLI access for deployment

1. Sign in to the console at the URL above as **`sandeep-admin`**.
2. Click your user name (top right) → **Security credentials** → **Create access key** (pick **CLI** / **Local code** if prompted).
3. Copy **Access Key ID** and **Secret Access Key** once (secret shown only at creation).
4. On your PC run:

   ```bash
   aws configure
   ```

   Paste the keys and set **Default region**: `ap-south-1`.

5. Verify:

   ```bash
   aws sts get-caller-identity
   ```

   You should see account `836809166355` and ARN ending with `user/sandeep-admin`.

If **`sandeep-admin`** has no permission to create EC2/RDS/etc., attach policies such as **AdministratorAccess** (only for initial provisioning) or narrower roles later.

## Useful ARN patterns

Replace `<user-or-role>` with your IAM user or role name:

```text
arn:aws:iam::836809166355:user/<user-or-role>
arn:aws:iam::836809166355:root
```

S3 bucket policy resource example:

```text
arn:aws:s3:::libraryconnekto-frontend/*
```

## Verify CLI is using this account

```bash
aws sts get-caller-identity
```

Expected `Account`: `836809166355`.

## Privacy & console settings

- Do **not** commit access keys, passwords, or PEM files.
- Add **Billing**, **Operations**, and **Security** alternate contacts in  
  **AWS Console → Account → Alternate contacts** so invoices and incidents reach the right people.
- Primary contact details (phone, address) belong only in the AWS Account console, not in git.

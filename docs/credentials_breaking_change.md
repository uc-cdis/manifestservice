# Breaking Change to ManifestService

## Summary

We are introducing a significant update to ManifestService, which currently acts as a proxy to an Amazon S3 bucket. To enhance our security posture, we're transitioning away from using AWS user credentials. This change will require updates to your configuration.

## Previous Method

Historically, the ManifestService required AWS credentials to be able to access the S3 bucket. These credentials were passed through a Kubernetes secret, which the service consumed.

## New Method

Starting in version 1.0.0/2023.07, ManifestService longer looks for AWS credentials in the configuration file. Instead, the service relies on credentials mounted to the pod. This change is implemented to ensure an improved security environment for the service.

### AWS EKS IRSA

We will now be utilizing the AWS EKS Identity Roles for Service Accounts (IRSA). This approach automounts AWS role credentials to a pod based on an EKS service account. This update aims to streamline the credentialing process and further secure access to the AWS S3 bucket.

**NOTE:** The use of AWS EKS IRSA is applicable if you're using AWS EKS.

### Non-EKS Users

For those not using AWS EKS, the method for mounting the credentials will need to change. The recommended way is to set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as environment variables in the pod.

In future iterations, we aim to include this feature in the Helm chart deployment to simplify the process.

## Action Required

Please update your setup to comply with this new security update. Should you face any issues or have any queries regarding this update, please feel free to reach out. We appreciate your understanding as we work together to enhance our security posture.

# Security Policy

All production workloads must use Microsoft Entra ID authentication. API keys
are permitted for local development only and must never be committed to source
control.

## Data classification

Data is classified as Public, Internal, Confidential, or Restricted. Restricted
data must be stored in resources with private endpoints enabled and customer
managed keys where required by regulation.

## Access reviews

Access to Confidential and Restricted systems is reviewed every quarter. The
review owner is the data steward for the affected system.

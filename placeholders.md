## Configuration & Secrets (Placeholders)

This repository includes **placeholder configuration files** required for local execution.
They are intentionally committed **without any real values**.

### Included Placeholder Files
- `.env` – Environment variable definitions
  
SNOWFLAKE_ACCOUNT=      
SNOWFLAKE_USER=      
SNOWFLAKE_ROLE=      
SNOWFLAKE_WAREHOUSE=      
SNOWFLAKE_DATABASE=      
SNOWFLAKE_SCHEMA=      
PRIVATE_KEY_PATH=      

- `rsa_key.p8` – RSA private key placeholder 
- `rsa_key.pub` – RSA public key placeholder 

### How to Use Locally
1. Open `.env` and populate the required variables with your own Snowflake credentials.
2. Generate your own RSA key pair and place the files locally as:
   - `rsa_key.p8`
   - `rsa_key.pub`
3. These files are **tracked only as placeholders**. Local changes are intentionally ignored to prevent accidental commits of sensitive data.

### Security Note
No credentials, private keys, or secrets are stored in this repository.
Users must supply their own secure configuration locally.

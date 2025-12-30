# Snowflake RSA Key-Pair Authentication Guide

## Overview
RSA key-pair authentication allows you to connect to Snowflake without passwords or MFA codes. This is the recommended method for automated scripts and production environments.

---

## Prerequisites

- Snowflake account with appropriate user privileges
- OpenSSL installed on your system
- Python with `snowflake-connector-python` and `cryptography` packages

```bash
pip install snowflake-connector-python cryptography
```

---

## Step 1: Generate RSA Key Pair

Open your terminal and run the following commands:

### Generate Private Key
```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
```

This creates an unencrypted 2048-bit RSA private key in PKCS#8 format.

### Generate Public Key
```bash
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
```

This extracts the public key from the private key.

**Output Files:**
- `rsa_key.p8` - Private key (keep secure, never share)
- `rsa_key.pub` - Public key (will be registered with Snowflake)

---

## Step 2: Extract Public Key Content

Display the public key content:

**Mac/Linux:**
```bash
cat rsa_key.pub
```

**Windows:**
```bash
type rsa_key.pub
```

**Output Example:**
```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1a2b3c4d...
...additional lines of base64 encoded key...
-----END PUBLIC KEY-----
```

**Copy only the content between the header and footer** (exclude `-----BEGIN PUBLIC KEY-----` and `-----END PUBLIC KEY-----` lines). Remove all line breaks to create a single continuous string.

---

## Step 3: Register Public Key in Snowflake

Log into Snowflake web UI (Snowsight) and execute:

```sql
ALTER USER <username> SET RSA_PUBLIC_KEY='<your_public_key_string>';
```

**Example:**
```sql
ALTER USER TANMAY9993 SET RSA_PUBLIC_KEY='MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1a2b3c4d5e6f7g8h9i0j...';
```

**Verify Registration:**
```sql
DESC USER <username>;
```

Look for the `RSA_PUBLIC_KEY_FP` property to confirm the key is registered.

---

## Step 4: Connect Using Python

### Basic Connection

```python
import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

# Load private key from file
with open("rsa_key.p8", "rb") as key_file:
    private_key = serialization.load_pem_private_key(
        key_file.read(),
        password=None,
        backend=default_backend()
    )

# Convert private key to DER format (required by Snowflake)
pkb = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Establish connection
conn = snowflake.connector.connect(
    account="<account_identifier>",
    user="<username>",
    private_key=pkb
)

# Test connection
cursor = conn.cursor()
cursor.execute("SELECT CURRENT_VERSION()")
print(cursor.fetchone()[0])

# Clean up
cursor.close()
conn.close()
```

### Connection with Additional Parameters

```python
conn = snowflake.connector.connect(
    account="",
    user="",
    private_key=pkb,
    warehouse="",
    database="",
    schema="",
    role=""
)
```

### Using Environment Variables

```python
import os
from dotenv import load_dotenv

load_dotenv()

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    private_key=pkb,
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA"),
    role=os.getenv("SNOWFLAKE_ROLE")
)
```

**.env file:**
```properties
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PRIVATE_KEY_PATH=
SNOWFLAKE_ROLE=
SNOWFLAKE_WAREHOUSE=
SNOWFLAKE_DATABASE=
SNOWFLAKE_SCHEMA=
```

---

## Security Best Practices

1. **Never commit private keys to version control**
   - Add `rsa_key.p8` to `.gitignore`
   - Store keys securely (e.g., AWS Secrets Manager, Azure Key Vault)

2. **Use encrypted private keys for production**
   ```bash
   # Generate encrypted private key
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key_encrypted.p8
   ```
   
   Then load with password:
   ```python
   private_key = serialization.load_pem_private_key(
       key_file.read(),
       password=b"your_password",
       backend=default_backend()
   )
   ```

3. **Rotate keys periodically**
   - Generate new key pair
   - Register new public key with Snowflake
   - Remove old public key after transition

4. **Set appropriate file permissions**
   ```bash
   chmod 600 rsa_key.p8  # Read/write for owner only
   ```

---

## Key Rotation

To rotate your RSA key pair:

```sql
-- Add new public key (Snowflake supports up to 2 keys)
ALTER USER <username> SET RSA_PUBLIC_KEY_2='<new_public_key>';

-- After verifying new key works, remove old key
ALTER USER <username> UNSET RSA_PUBLIC_KEY;

-- Promote key 2 to primary
ALTER USER <username> SET RSA_PUBLIC_KEY='<new_public_key>';
ALTER USER <username> UNSET RSA_PUBLIC_KEY_2;
```

---

## Troubleshooting

### Error: "JWT token is invalid"
- Verify public key is correctly registered in Snowflake
- Ensure private key file path is correct
- Check that private and public keys match

### Error: "Private key file not found"
- Verify file path in your code
- Ensure `rsa_key.p8` is in the correct directory
- Use absolute path if needed

### Error: "Failed to load private key"
- Check file permissions
- Verify key format (should be PKCS#8)
- If encrypted, provide correct password

### Account Identifier Format
- Use lowercase: `orgname-accountname` or `account_locator`
- Example: `rnswfmx-cd10010`
- Find your account identifier:
  ```sql
  SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME();
  ```

---

## Advantages of Key-Pair Authentication

✓ **No MFA required** - Bypasses multi-factor authentication  
✓ **No password management** - No expiration or reset issues  
✓ **More secure** - Private key never transmitted over network  
✓ **Ideal for automation** - No human interaction needed  
✓ **Industry standard** - Same technology as SSH, GitHub, AWS  

---

## Complete Example Script

```python
import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import pandas as pd

def connect_to_snowflake(private_key_path, account, user):
    """
    Establish Snowflake connection using RSA key-pair authentication.
    
    Args:
        private_key_path: Path to private key file
        account: Snowflake account identifier
        user: Snowflake username
    
    Returns:
        snowflake.connector.connection object
    """
    # Load private key
    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )
    
    # Convert to DER format
    pkb = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Connect
    conn = snowflake.connector.connect(
        account=account,
        user=user,
        private_key=pkb
    )
    
    return conn

# Usage
if __name__ == "__main__":
    conn = connect_to_snowflake(
        private_key_path="rsa_key.p8",
        account="",
        user=""
    )
    
    # Execute query
    query = "SELECT * FROM INVENTORY_DB.PUBLIC.YOUR_TABLE LIMIT 10"
    df = pd.read_sql(query, conn)
    print(df)
    
    # Close connection
    conn.close()
```

---

## References

- [Snowflake Documentation: Key Pair Authentication](https://docs.snowflake.com/en/user-guide/key-pair-auth)
- [Snowflake Python Connector](https://docs.snowflake.com/en/user-guide/python-connector)
- [OpenSSL Documentation](https://www.openssl.org/docs/)

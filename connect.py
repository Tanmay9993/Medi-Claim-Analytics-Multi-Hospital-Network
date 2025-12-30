import os
from dotenv import load_dotenv
import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import pandas as pd

# Load environment variables from .env
load_dotenv(override=True)


def get_snowflake_connection():
    """Create and return a Snowflake connection using key-pair auth."""
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    role = os.getenv("SNOWFLAKE_ROLE")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    database = os.getenv("SNOWFLAKE_DATABASE")
    schema = os.getenv("SNOWFLAKE_SCHEMA")
    private_key_path = os.getenv("PRIVATE_KEY_PATH")

    if not all([account, user, role, warehouse, database, schema, private_key_path]):
        raise ValueError("One or more Snowflake environment variables are missing.")

    # Load private key
    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )

    # Convert private key to DER bytes
    pkb = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    conn = snowflake.connector.connect(
        account=account,
        user=user,
        private_key=pkb,
        role=role,
        warehouse=warehouse,
        database=database,
        schema=schema,
    )
    with conn.cursor() as cur:
        cur.execute(f"USE WAREHOUSE {warehouse}")
        cur.execute(f"USE DATABASE {database}")
        cur.execute(f"USE SCHEMA {schema}")

    return conn




def run_query(query: str, params: dict | None = None) -> pd.DataFrame:
    """
    Run a SQL query on Snowflake and return a pandas DataFrame.
    Opens and closes the connection for each call.
    """
    conn = get_snowflake_connection()
    try:
        with conn.cursor() as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            rows = cur.fetchall()
            columns = [col[0] for col in cur.description]
    finally:
        conn.close()

    return pd.DataFrame(rows, columns=columns)


if __name__ == "__main__":
    # Small runtime check: try to create a connection and print status.
    try:
        conn = get_snowflake_connection()
        print("Snowflake connection established for account:", os.getenv("SNOWFLAKE_ACCOUNT"))
        try:
            conn.close()
        except Exception:
            pass
    except Exception as exc:
        # Print a full traceback to help debugging missing env or key issues.
        import traceback
        traceback.print_exc()
        print("Snowflake connection failed:", str(exc)) 

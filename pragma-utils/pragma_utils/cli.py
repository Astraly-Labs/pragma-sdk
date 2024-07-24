import os

from typing import Union, Tuple

from pragma_utils.aws import fetch_aws_private_key


def load_private_key_from_cli_arg(private_key: str) -> Union[str, Tuple[str, str]]:
    """
    Load the private key either from AWS, environment variable, from the provided plain value, or return keystore info.

    Args:
        private_key: The private key string, prefixed with 'aws:', 'plain:', 'env:', or 'keystore:'.

    Returns:
        Union[str, Tuple[str, str]]:
        - For 'aws:', 'plain:', 'env:': returns the loaded private key as a string.
        - For 'keystore:': returns a tuple of (path, password).

    Raises:
        ValueError: If the private key prefix is invalid or if the keystore information is incorrect.
    """
    if private_key.startswith("aws:"):
        secret_name = private_key.split("aws:", 1)[1]
        return fetch_aws_private_key(secret_name)
    elif private_key.startswith("plain:"):
        return private_key.split("plain:", 1)[1]
    elif private_key.startswith("env:"):
        env_var_name = private_key.split("env:", 1)[1]
        return os.environ[env_var_name]
    elif private_key.startswith("keystore:"):
        keystore_info = private_key.split("keystore:", 1)[1]
        try:
            path, password = keystore_info.rsplit(":", 1)
            return (path.strip(), password.strip())
        except ValueError:
            raise ValueError("Keystore format should be 'keystore:PATH:PASSWORD'")
    else:
        raise ValueError(
            "Private key must be prefixed with either 'aws:', 'plain:', 'env:', or 'keystore:'"
        )

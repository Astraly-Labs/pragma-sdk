# Checkpointer

Service used to automatically create checkpoints periodically for a set of pairs.

### Usage

The service is ran through the CLI.

To specify for which assets you want to set checkpoints, you will need to provide a yaml configuration file formatted as follow:

```yaml
# config/config.example.yaml
spot:
  - pair: BTC/USD
  - pair: ETH/USD

future:
  - pair: BTC/USD
    expiry: 102425525524
    # You can have the same pair multiple time for different expiries
  - pair: BTC/USD
    expiry: 0
  - pair: ETH/USD
    expiry: 234204249042
  - pair: SOL/USD
    expiry: 0
```

For spot pairs, we simply list them, but for future ones, you need to add for which expiry timestamp you wish to create new checkpoints.

To have more information on how to run the CLI, you can use the `--help` command:

```bash
.venv ❯ python checkpointer/main.py --help

Usage: main.py [OPTIONS]

  Checkpoints setter entry point.

Options:
  -c, --config-file PATH          Path to YAML configuration file.  [required]
  
  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Logging level.
  
  -n, --network [sepolia|mainnet]
                                  On which networks the checkpoints will be
                                  set. Defaults to SEPOLIA.  [required]
  
  --rpc-url TEXT                  RPC url used by the onchain client.
  
  --oracle-address TEXT           Address of the Pragma Oracle  [required]
  
  --admin-address TEXT            Address of the Admin contract for the
                                  Oracle.  [required]
  
  -p, --private-key TEXT          Secret key of the signer. Format:
                                  aws:secret_name, plain:secret_key, or
                                  env:ENV_VAR_NAME  [required]
  
  -t, --set-checkpoint-interval
                                  Delay in minutes between each new
                                  checkpoints. Defaults to 60 minutes.  [x>=0]
  
  -help                          Show this message and exit.
```

For example:

```sh
poetry run checkpointer -c config/config.example.yaml --oracle-address $PRAGMA_ORACLE_ADDRESS --admin-address $PRAGMA_ADMIN_ACCOUNT -p plain:$MY_PRIVATE_KEY
```

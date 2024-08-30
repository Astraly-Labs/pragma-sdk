# VRF Listener

Service used to listen for VRF requests and handle them.

## Usage

The service is ran through the CLI, to have more information you can use the `--help` command:

```bash
.venv ❯ python vrf_listener/main.py --help

Usage: main.py [OPTIONS]

Options:
  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Logging level.

  -n, --network [sepolia|mainnet|devnet]
                                  Which network to listen. Defaults to
                                  SEPOLIA.  [required]

  --rpc-url TEXT                  RPC url used by the onchain client.

  --vrf-address TEXT              Address of the VRF contract  [required]

  --admin-address TEXT            Address of the Admin contract  [required]

  -p, --private-key TEXT          Secret key of the signer. Format:
                                  aws:secret_name, plain:secret_key, or
                                  env:ENV_VAR_NAME  [required]

  -b--start-block INTEGER RANGE   At which block to start listening for VRF
                                  requests. Defaults to 0.  [x>=0]

  -t, --check-requests-interval   Delay in seconds between checks for VRF
                                  requests. Defaults to 10 seconds.  [x>=0]

  --help                          Show this message and exit.
```

For example:

```sh
poetry run vrf_listener --vrf-address $PRAGMA_VRF_CONTRACT --admin-address $PRAGMA_ORACLE_ADMIN --private-key plain:$PRAGMA_ADMIN_PV_KEY
```

Will start listening for VRF requests on Sepolia every 10 seconds since block 0.

## Benchmarking

We have created a small script to check the performances of the VRF listener performances.

To run it, simply do:

```bash
poe benchmark -n devnet --txs-per-user 5
```

This will spawn a local devnet and sends 5 VRF requests per user.

The script is also runnable for sepolia, see:

```bash
poe benchmark --help

Usage: main.py [OPTIONS]

  VRF Benchmark entry point.

Options:
  -n, --network [devnet|sepolia|mainnet]
                                  Which network to listen. Defaults to
                                  SEPOLIA.  [required]

  --rpc-url TEXT                  RPC url used by the onchain client.
                                  
  --vrf-address TEXT              Address of the VRF contract
                                  
  -c, --config-file PATH          Path to YAML accounts configuration file.
                                  Contains the accounts to use.
                                  
  --txs-per-user INTEGER RANGE    VRF requests sent per user.  [x>=1]
                                  
  --help                          Show this message and exit.
```

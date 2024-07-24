# Price pusher


## Usage

The price-pusher service is ran through the ClI, to have more information you can use the `--help` command:

```bash
.venv ❯ python price_pusher/main.py --help

Usage: main.py [OPTIONS]
Options:

  -c, --config-file PATH          Path to YAML configuration file.  [required]

  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Logging level.

  -t, --target [onchain|offchain]
                                  Where the prices will be published.
                                  [required]

  -n, --network [sepolia|mainnet]
                                  At which network the price corresponds.
                                  [required]

  -p, --private-key TEXT          Secret key of the signer. Format:
                                  aws:secret_name, plain:secret_key, or
                                  env:ENV_VAR_NAME  [required]

  --publisher-name TEXT           Your publisher name.  [required]

  --publisher-address TEXT        Your publisher address.  [required]

  --api-base-url TEXT             Pragma API base URL

  --api-key TEXT                  Pragma API key used to publish offchain

  --help                          Show this message and exit
```

For example, if you wish to run the `price-pusher` for our offchain API, that would be:

```sh
poetry run price_pusher -c ./config/config.example.yaml --log-level DEBUG -t offchain -n mainnet -p plain:$PUBLISHER_PV_KEY --publisher-name $PUBLISHER_NAME --publisher-address $PUBLISHER_ADDRESS --api-key $PRAGMA_OFFCHAIN_API_KEY --api-base-url http://localhost:3000
```

## Architecture

![Architecture Diagram](diagram.png)

(Not 100% up to date and accurate with the latest changes, but the overall view is correct).

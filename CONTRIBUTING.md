# Contributing

## Setup

1. Clone the `pragma-sdk` repository:
```shell
git clone git@github.com:Astraly-Labs/pragma-sdk.git
```
2. Install dependencies with Poetry:
```shell
poetry install
```

## Running Tests Locally

1. Clone the Cairo repository:
```shell
git clone https://github.com/starkware-libs/cairo && cd cairo
```
2. Checkout the release tag:
```shell
git checkout v2.2.0
```
3. Compile:
```shell
cargo b --bin starknet-compile
cargo b --bin starknet-sierra-compile
```
4. In the tests directory (`cd ./pragma/tests/`), add the path to Cairo on your local machine.
```shell
echo "/path/to/cairo/Cargo.toml" >> manifest-path
```
5. Now, you can run tests:
```shell
poetry run coverage run -m pytest --net=devnet --client=full_node -v --reruns 5 --only-rerun aiohttp.client_exceptions.ClientConnectorError pragma/tests -s
```

## Updating ABIs

1. Upgrade submodule
```shell
git submodule update --remote
```

2. Compile contracts
```shell
cd pragma-oracle && scarb build
```

3. Update ABIs
```shell
poe update_abis
```
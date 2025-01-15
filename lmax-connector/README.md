# LMAX Connector

A service that connects to LMAX Exchange via FIX 4.4 protocol and pushes EUR/USD market data to Pragma.

## Prerequisites

- Python 3.11+
- stunnel (for SSL/TLS connection to LMAX)
- LMAX Exchange account credentials
- uv for dependency management

## Installation

1. Install stunnel:

```bash
# macOS
brew install stunnel

# Ubuntu/Debian
apt-get install stunnel4
```

2. Install the package:

```bash
uv sync
```

## Configuration

1. Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

2. Configure stunnel by modifying `stunnel.conf`:

```ini
; Stunnel configuration for LMAX FIX connection
debug = 7
socket = l:TCP_NODELAY=1
socket = r:TCP_NODELAY=1
fips = no

[Production-MarketData]
client = yes
accept = 127.0.0.1:40003
connect = fix-md.lmaxtrader.com:443
sslVersion = TLSv1.2
verify = 0
delay = no
TIMEOUTclose = 0
```

## Running the Service

1. Start stunnel:

```bash
cd lmax-connector
stunnel stunnel.conf
```

2. Then, start the connector:

```bash
python -m lmax_connector
```

The service will:

1. Connect to LMAX via FIX 4.4 protocol
2. Subscribe to EUR/USD market data
3. Push prices to Pragma API

## Environment Variables

- `LMAX_SENDER_COMP_ID`: Your LMAX username
- `LMAX_TARGET_COMP_ID`: LMXBLM (for production)
- `LMAX_PASSWORD`: Your LMAX password
- `PRAGMA_API_KEY`: Your Pragma API key
- `PRAGMA_ACCOUNT_PRIVATE_KEY`: Your Pragma account private key
- `PRAGMA_ACCOUNT_CONTRACT_ADDRESS`: Your Pragma account contract address

## Using Docker

1. Build the Docker image:

```bash
ddocker build -t lmax-connector:latest -f lmax-connector/Dockerfile .
```

2. Run the Docker container:

```bash
docker run -v ./config:/opt/lmax-connector/config --env-file .env lmax-connector
```

## Troubleshooting

1. If you see SSL/TLS connection errors, make sure stunnel is running and the configuration is correct.
2. If you see authentication errors, verify your LMAX credentials in the `.env` file.
3. Check the logs in `log/` directory for detailed error messages.

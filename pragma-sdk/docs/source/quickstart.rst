Quickstart
==========

This is a quickstart guide to get you up and running with the Pragma SDK.

Fetch data
---------------

To fetch data on 3rd parties API, one can use the `FetcherClient`.

Here is step by step example:

.. code-block:: python

    from pragma_sdk.common.fetchers import FetcherClient
    from pragma_sdk.common.fetchers.fetchers import BitstampFetcher, GateIOFetcher

    # 1. Create a list of pairs that you want to fetch
    pairs = [
        Pair.from_tickers("BTC","USD"),
        Pair.from_tickers("ETH","USD"),
    ]

    # 2. Create your fetchers and add them to the FetcherClient
    bitstamp_fetcher = BitstampFetcher(pairs, "publisher_test")
    gateio_fetcher = GateIOFetcher(pairs, "publisher_test")
    fetchers = [
        bitstamp_fetcher,
        gateio_fetcher,
    ]

    fc = FetcherClient()
    fc.add_fetchers(fetchers)

    # 3. Fetch the data
    entries = await fc.fetch()

.. hint::

    If you are experiencing issues with fetching, it's most likely due to the fetcher not being able to connect to the API.
    Some fetchers do require ``api_key`` keyword argument in their constructor. 
    Please refer to the fetcher's documentation for more information.
    Also if you want to fetch data synchronously, you can use the :meth:`fetch_sync` method.

Interact with pragma on-chain
-----------------------------

To interact with the Pragma on-chain, one can use the `PragmaOnChainClient`.
The client covers most of the external endpoints of the Pragma on-chain contracts.
Please refer to the complete `documentation <https://docs.pragma.build/Resources/Cairo%201/data-feeds/consuming-data>`_

Here is an example :

.. code-block:: python

    from pragma_sdk.onchain.client import PragmaOnChainClient
    from pragma_sdk.common.types.pair import Pair
    from pragma_sdk.common.types.types import AggregationMode, DataTypes
    from pragma_sdk.common.types.asset import Asset 

    # Create your client
    poc = PragmaOnChainClient(
        network="mainnet", # defaults to sepolia
    )

    # Get spot data
    data = await poc.get_spot(
        'BTC/USD', 
        AggregationMode.Median,
        ['FOURLEAF', 'MECX', 'FLOWDESK'],
        block_number=12345678 # defaults to latest
    )

    print(f"Retrieved BTC/USD price data: {data.price}.
    {data.num_sources_aggregated} sources aggregated.")

    # Get all sources for spot 'ETH/USD'
    sources = await poc.get_all_sources(
        Asset(DataTypes.SPOT, 'ETH/USD')
    )

.. hint::

    If you are interacting with contracts locally or on a custom network, you can specify a custom 
    RPC url in the `network` parameter of the `PragmaOnChainClient` constructor.
    In that case make sure to specify the `chain_name`.
    You can also specify addresses of contracts with the `account_contract_address` argument. 


Interact with pragma off-chain
------------------------------

To interact with the Pragma off-chain, one can use the `PragmaOffChainClient<pragma_sdk.offchain.client.PragmaOffChainClient>`.
The client covers most of the external endpoints of the Pragma off-chain API.
Please refer to the complete `api documentation <https://docs.pragma.build/Resources/PragmApi/overview>`_

An API key is currently needed to interact with the off-chain API. You can get one by contacting us at `support@pragma.build`.

.. code-block:: python

    from pragma_sdk.offchain.client import PragmaAPIClient
    from pragma_sdk.common.types.pair import Pair
    from pragma_sdk.common.types.types import AggregationMode, DataTypes
    from pragma_sdk.common.types.asset import Asset 

    # Create your client
    pac = PragmaAPIClient(
        api_base_url="https://api.dev.pragma.build",
        api_key="your_api_key"
    )

    # Get 1min OHLC data
    entries = await poc.get_ohlc(
        'BTC/USD', 
        None,
        Interval.ONE_MINUTE,
        AggregationMode.Median,
    )
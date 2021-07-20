import dataclasses
from json import JSONDecodeError
from typing import Optional, Any

import requests


@dataclasses.dataclass
class SocialData:
    mentions: int
    """The number of times given stock has been mentioned on social platform"""
    sentiment: float
    """The average sentiment score of remarks mentioning this stock"""
    relative_hype: Optional[float]
    """How many times more frequently has this stock been mentioned than other stocks"""

    def __init__(self, results: dict[str, Any], platform: str):
        self.mentions = results.get(f"{platform}_mentions")
        self.sentiment = results.get(f"{platform}_sentiment")
        self.relative_hype = results.get(f"{platform}_relative_hype")


@dataclasses.dataclass
class Subreddit:
    mentions: int
    """The number of times given stock has been mentioned on this subreddit"""
    sentiment: float
    """The average sentiment score of remarks mentioning this stock"""


@dataclasses.dataclass
class Reddit:
    posts: SocialData
    """Analysis for Reddit posts mentioning this ticker"""
    comments: SocialData
    """Analysis for Reddit comments mentioning this ticker"""
    subreddits: dict[str, Subreddit]
    """A dictionary of subreddits"""


@dataclasses.dataclass
class TickerData:
    """
    Specifies a basic data item for a specific ticker.

    .. attention:: Do not try to initialise one yourself.

    .. versionchanged:: 1.1.0
    """

    symbol: str
    """Ticker symbol"""
    sentiment: float
    """Positive sentiment (%)"""
    AHI: float
    """Average Hype Index"""
    RHI: float
    """Relative Hype Index"""
    SGP: float
    """Standard General Perception"""

    def __init__(self, symbol: str, results: dict):
        self.symbol = symbol

        for field in ['sentiment', 'AHI', 'RHI', 'SGP']:
            setattr(self, field, results.get(field))


@dataclasses.dataclass
class QuoteData(TickerData):
    """
    .. attention:: Returned by quote, do not try to initialise one yourself.
    """

    reddit_data: Reddit
    """Analysis for Reddit data"""
    tweets: SocialData
    """Analysis for Twitter"""
    stocktwits_posts: SocialData
    """Analysis for Stocktwits posts"""
    yahoo_finance_comments: SocialData
    """Analysis for Yahoo! Finance comments"""

    def __init__(self, symbol: str, results: dict):
        super().__init__(symbol, results)

        for platform in ['tweet', 'stocktwits_post', 'yahoo_finance_comment']:
            setattr(self, f"{platform}s", SocialData(results, platform))

        subreddits_processed = None
        if 'subreddits' in results:
            subreddits = results.get("subreddits")
            mentions = subreddits.get("reddit_subreddit_mentions")
            sentiment = subreddits.get("reddit_subreddit_sentiment")
            subreddits_processed = {
                subreddit_name: Subreddit(
                    mentions=mentions[subreddit_name],
                    sentiment=sentiment[subreddit_name]
                ) for subreddit_name in (mentions.keys() & sentiment.keys())
            }

        self.reddit_data = Reddit(
            posts=SocialData(results, "reddit_post"),
            comments=SocialData(results, "reddit_comment"),
            subreddits=subreddits_processed
        )


class Sentipy:
    """
    The Sentipy module provides a simple and lightweight way to interact with the SentimentInvestor API and data.

    Sentipy is installed through [pip](https://pip.pypa.io/)
    ```
    $ python3 -m pip install sentiment-investor
    ```
    """

    base_url = r"https://api.sentimentinvestor.com/v4/"
    """
    The base URL of the SentimentInvestor API
    """

    def __init__(self, token: str = None, key: str = None):
        """
        Initialise a new SentiPy instance with your token and key

        Examples:
            >>> token = "my-very-secret-token"
            >>> key = "my-very-secret-key"
            >>> sentipy = Sentipy(token=token, key=key)

        Args:
            token (str): API token from the SentimentInvestor website
            key (str): API key from the SentimentInvestor website

        Raises:
            `ValueError` if either `token` or `key` not provided
        """
        if token is None or key is None:
            raise ValueError(
                "Please provide a token and key - these can be obtained at "
                "https://sentimentinvestor.com/developer/dashboard")
        self.token = token
        self.key = key

    def __base_request(self, endpoint: str, params: dict[str, Any] = None) -> dict:
        """
        Make a request to a specific REST endpoint on the SentimentInvestor API

        Args:
            endpoint (str): the REST endpoint (final fragment in URL)
            params (dict): any supplementary parameters to pass to the API

        Returns: the JSON response if the request was successful, otherwise None

        """
        if params is None:
            params = {}
        url = self.base_url + endpoint
        params["token"] = self.token
        params["key"] = self.key
        response = requests.get(url, params)
        if response.content.decode("utf-8") == 'invalid_parameter' \
                or response.content.decode("utf-8") == 'incorrect_key':
            raise ValueError("Incorrect key or token")
        else:
            try:
                json = response.json()
            except JSONDecodeError:
                raise Exception(response.text)

            if response.ok:
                return json
            else:
                raise Exception(json.get("message"))

    def parsed(self, symbol: str) -> TickerData:
        """
        The parsed data endpoints provides the four core metrics for a stock: AHI, RHI, SGP and sentiment.

        Args:
            symbol (str): string specifying the ticker or symbol of the stock to request data for

        Returns: a QuoteData object
        
        Examples:
            >>> parsed_data = sentipy.parsed("AAPL")
            >>> print(parsed_data.AHI)
            0.8478140394088669

        .. versionadded:: 1.1.0
        """
        params = {
            "symbol": symbol
        }
        response = self.__base_request("parsed", params=params)
        return TickerData(response.get("symbol"), response.get("results")) if response.get("success") else None

    def raw(self, symbol: str) -> QuoteData:
        """
        The raw data endpoint provides access to raw data metrics for the monitored social platforms

        Args:
            symbol (str): ticker or symbol of the stock to request data for

        Returns: a QuoteData object

        .. versionadded:: 1.1.0
        """
        params = {
            "symbol": symbol
        }
        response = self.__base_request("raw", params=params)
        return QuoteData(response.get("symbol"), response.get("results")) if response.get("success") else None

    def quote(self, symbol: str, enrich: bool = False) -> QuoteData:
        """
        The quote data endpoint provides access to all realtime data about stocks along with further data if requested

        Args:
            symbol (str): ticker or symbol of the stock to request data for
            enrich (bool): whether to request enriched data

        Returns: a QuoteData object

        Examples:
            >>> quote_data = sentipy.quote("TSLA", enrich=True)
            >>> print([var for var in dir(quote_data) if not var.startswith("_")])
            ['AHI',
             'RHI',
             'reddit_comment_mentions',
             'reddit_comment_relative_hype',
             'reddit_comment_sentiment',
             'reddit_post_mentions',
             'reddit_post_relative_hype',
             'reddit_post_sentiment',
             'sentiment',
             'stocktwits_post_mentions',
             'stocktwits_post_relative_hype',
             'stocktwits_post_sentiment',
             'subreddits',
             'success',
             'symbol',
             'tweet_mentions',
             'tweet_relative_hype',
             'yahoo_finance_comment_mentions',
             'yahoo_finance_comment_relative_hype',
             'yahoo_finance_comment_sentiment']
            >>> print(quote_data.reddit_comment_mentions)
            20
            >>> print(quote_data.subreddits) # only for 'enriched' requests
            {'reddit_subreddit_mentions': {'WallStreetBetsELITE': 1,
                                           'investing': 2,
                                           'smallstreetbets': 1,
                                           'stocks': 10,
                                           'wallstreetbets': 7},
             'reddit_subreddit_sentiment': {'WallStreetBetsELITE': 1,
                                            'investing': 0,
                                            'smallstreetbets': 0,
                                            'stocks': 0.8,
                                            'wallstreetbets': 0.5}}
        """
        params = {
            "symbol": symbol,
            "enrich": enrich
        }
        response = self.__base_request("quote", params=params)
        return QuoteData(response.get("symbol"), response.get("results")) if response.get("success") else None

    def sort(self, metric: str, limit: int) -> list[TickerData]:
        """
        The sort data endpoint provides access to ordered rankings of stocks across core metrics

        Args:
            metric (str): the metric by which to sort the stocks
            limit (int): the maximum number of stocks to return

        Returns: a list of TickerData objects

        Examples:
            >>> metric = "AHI"
            >>> limit = 4
            >>> sort_data = sentipy.sort(metric, limit)
            >>> for ticker in sort_data:
            ...     print(ticker)
            ...
            {'AHI': 1.9201046798029555, 'RHI': 1.2556815851300576, 'rank': 0, 'reddit_comment_mentions': 59, 'reddit_post_mentions': 0, 'sentiment': 0.7080172560355916, 'stocktwits_post_mentions': 171, 'subreddits': {'symbol': 'AMC'}, 'symbol': 'AMC', 'tweet_mentions': 149, 'yahoo_finance_comment_mentions': 396}
            {'AHI': 1.833990147783251, 'RHI': 1.506333195051962, 'rank': 1, 'reddit_comment_mentions': 4, 'reddit_post_mentions': 0, 'sentiment': 0.925215723873442, 'stocktwits_post_mentions': 508, 'subreddits': {'symbol': 'ET'}, 'symbol': 'ET', 'tweet_mentions': 0, 'yahoo_finance_comment_mentions': 0}
            {'AHI': 1.3133928571428573, 'RHI': 1.0435689663713186, 'rank': 2, 'reddit_comment_mentions': 58, 'reddit_post_mentions': 0, 'sentiment': 0.7033474218089603, 'stocktwits_post_mentions': 262, 'subreddits': {'symbol': 'SPY'}, 'symbol': 'SPY', 'tweet_mentions': 20, 'yahoo_finance_comment_mentions': 3}
            {'AHI': 0.8098830049261084, 'RHI': 1.4870815942458393, 'rank': 3, 'reddit_comment_mentions': 62, 'reddit_post_mentions': 0, 'sentiment': 0.7574809805579037, 'stocktwits_post_mentions': 113, 'subreddits': {'symbol': 'AAPL'}, 'symbol': 'AAPL', 'tweet_mentions': 20, 'yahoo_finance_comment_mentions': 13}
        """
        params = {
            "metric": metric,
            "limit": limit
        }
        response = self.__base_request("sort", params=params)
        return [TickerData(stock.get("symbol"), stock) for stock in response.get("results")] if response.get(
            "success") else None

    def historical(self, symbol: str, metric: str, start: int, end: int) -> dict[float, float]:
        """
        The historical data endpoint provides access to historical data for stocks

        Args:
            symbol (str): the stock to look up historical data for
            metric (str): the metric for which to return data
            start (int): Unix epoch timestamp in seconds specifying start of date range
            end (int): Unix epoch timestamp in seconds specifying end of date range

        Returns (dict): a dictionary of (timestamp -> data entry) mappings.

        Examples:
            >>> historical_data = sentipy.historical("AAPL", "RHI", 1614556869, 1619654469)
            >>> for timestamp, value in sorted(historical_data.items()):
            ...     print(timestamp, value)
            ...
            1618057166.5252028 5.9384505075115675e-05
            1618336173.950567 0.0004624613455115948
            1618338607.466995 0.0005780098550856681
            (...lots of lines omitted)

        """
        params = {
            "symbol": symbol,
            "metric": metric,
            "start": start,
            "end": end
        }
        response = self.__base_request("historical", params=params)
        return {dp.get("timestamp"): dp.get("data") for dp in response.get("results")} \
            if response.get("success") else None

    def bulk(self, symbols: list[str], enrich: bool = False) -> list[TickerData]:
        """
        Get quote data for several stocks simultaneously
        
        Args:
            symbols (iterable): list of stocks to get quote data for
            enrich (bool): whether to get enriched data
            
        Returns: a list of TickerData objects

        .. versionadded:: 1.1.0
        """
        params = {
            "symbols": ",".join(symbols),
            "enrich": enrich
        }
        response = self.__base_request("bulk", params=params)
        return [TickerData(stock.get("symbol"), stock) for stock in response.get("results")] if response.get(
            "success") else None

    def all(self, enrich: bool = False) -> list[TickerData]:
        """
        Get all data for all stocks simultaneously. 

        .. note:: this blocking call takes a long time to execute.

        Args:
            enrich (bool): whether to fetch enriched data

        Returns: a list of TickerData objects

        .. versionadded:: 1.1.0
        """
        params = {
            "enrich": enrich
        }
        response = self.__base_request("all", params=params)
        return [TickerData(stock.get("symbol"), stock) for stock in response.get("results")] if response.get(
            "success") else None

    def supported(self, symbol: str):
        """
        Query whether SentimentInvestor has data for a specified stock

        Args:
            symbol (str): stock ticker symbol to query

        Returns: boolean whether supported or not

        Examples:
            >>> for stock in ["AAPL", "TSLA", "SNTPY"]:
            ...     print(f"{stock} {'is' if sentipy.supported(stock) else 'is not'} supported.")
            ...
            AAPL is supported.
            TSLA is supported.
            SNTPY is not supported.

        .. versionadded:: 1.1.0
        """
        response = self.__base_request("supported", params={"symbol": symbol})
        return response.get("result") if response.get("success") else None

    def all_stocks(self) -> set[str]:
        """
        Get a list of all stocks for which Sentiment gather data

        Returns (iterable): list of stock symbols

        .. versionadded:: 1.1.0
        """
        response = self.__base_request("all-stocks")
        return set(response.get("results")) if response.get("success") else None

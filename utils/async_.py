import asyncio
import concurrent.futures
from typing import Literal, Optional, Union, Callable, Coroutine, Any

import aiohttp


def run_sync(coro: Coroutine):
    """
    Run a coroutine synchronously
    
    Parameters
    ----------
    coro : Coroutine
        The coroutine to run
        
    Returns
    -------
    Any
        The result of the coroutine
    """
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, coro)
        concurrent.futures.wait([future])
        return future.result()


async def run_async(func: Callable):
    """
    Run a synchronous function asynchronously
    
    Parameters
    ----------
    func : Callable
        The function to run
    
    Returns
    -------
    Any
        The result of the function
    """
    return await asyncio.get_event_loop().run_in_executor(None, func)


class AsyncTimer:
    """
    Class to create an asynchronous timer

    Attributes
    ----------
    is_running : bool
        Whether the timer is running or not
    
    Methods
    -------
    start
        A method that starts the timer
    cancel
        A method that cancel the timer
    restart
        A method that restart the timer

    Parameters
    ----------
    delay : Union[int, float]
        The delay of the timer
    callback : Callable
        The callback to call after the delay
    *args
        The arguments for the callback
    **kwargs
        The keyword arguments for the callback
    """

    def __init__(self, delay: Union[int, float], callback: Callable, *args, **kwargs):
        self._delay = delay
        self._callback = callback
        self._args = args
        self._kwargs = kwargs
        self._future = None

    async def _job(self):
        await asyncio.sleep(self._delay)
        if asyncio.iscoroutinefunction(self._callback):
            await self._callback(*self._args, **self._kwargs)
        else:
            self._callback(*self._args, **self._kwargs)

    def start(self):
        """
        Start the timer
        """
        with concurrent.futures.ThreadPoolExecutor() as pool:
            self._future = pool.submit(run_sync, self._job())

    def cancel(self):
        """
        Cancel the timer
        """
        if self._future is not None:
            self._future.cancel()
            self._future = None

    @property
    def is_running(self):
        """
        Whether the timer is running or not
        """
        return self._future is not None and not self._future.done()

    def restart(self):
        """
        Restart the timer
        """
        self.cancel()
        self.start()


class AsyncRequests:
    """
    Class to make asynchronous requests

    Methods
    -------
    get
        Make a GET request
    post
        Make a POST request
    """

    @staticmethod
    async def get(url: str, params: Optional[dict] = None, data: Any = None, headers: Optional[dict] = None,
                  cookies: Optional[dict] = None, auth: Optional[aiohttp.BasicAuth] = None,
                  allow_redirects: bool = True, timeout: Optional[float] = None, json: Any = None,
                  return_type: Literal["json", "text", "content"] = "json") -> Union[dict, str, bytes]:
        """
        Make a GET request
        
        Parameters
        ----------
        url : str
            The URL to make the request to.
        params : Optional[dict]
            The parameters for the request. Default is None.
        data : Any
            The data for the request. Default is None.
        headers : Optional[dict]
            The headers for the request. Default is None.
        cookies : Optional[dict]
            The cookies for the request. Default is None.
        auth : Optional[aiohttp.BasicAuth]
            The authentication data for the request. Default is None.
        allow_redirects : bool
            Whether to allow redirects or not. Default is True.
        timeout : Optional[float]
            The timeout for the request. Default is None.
        json : Any
            The json data for the request. Default is None.
        return_type : Literal["json", "text", "content"]
            The type of the return value. Default is "json".
        
        Returns
        -------
        Union[dict, str, bytes]
            The response of the request
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, data=data, headers=headers, cookies=cookies, auth=auth,
                                   allow_redirects=allow_redirects, timeout=timeout, json=json) as response:
                response.raise_for_status()
                match return_type:
                    case "json":
                        return await response.json()
                    case "content":
                        return await response.content.read()
                    case _:
                        return await response.text()

    @staticmethod
    async def post(url: str, data: Any = None, json: Any = None, params: Optional[dict] = None,
                   headers: Optional[dict] = None, cookies: Optional[dict] = None,
                   auth: Optional[aiohttp.BasicAuth] = None, allow_redirects: bool = True,
                   timeout: Optional[float] = None, return_type: Literal["json", "text", "content"] = "json") \
            -> Union[dict, str, bytes]:
        """
        Make a POST request
        
        Parameters
        ----------
        url : str
            The URL to make the request to.
        data : Any
            The data for the request. Default is None.
        json : Any
            The json data for the request. Default is None.
        params : Optional[dict]
            The parameters for the request. Default is None.
        headers : Optional[dict]
            The headers for the request. Default is None.
        cookies : Optional[dict]
            The cookies for the request. Default is None.
        auth : Optional[aiohttp.BasicAuth]
            The authentication data for the request. Default is None.
        allow_redirects : bool
            Whether to allow redirects or not. Default is True.
        timeout : Optional[float]
            The timeout for the request. Default is None.
        return_type : Literal["json", "text", "content"]
            The type of the return value. Default is "json".
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, json=json, params=params, headers=headers, cookies=cookies,
                                    auth=auth, allow_redirects=allow_redirects, timeout=timeout) as response:
                response.raise_for_status()
                match return_type:
                    case "json":
                        return await response.json()
                    case "content":
                        return await response.content.read()
                    case _:
                        return await response.text()

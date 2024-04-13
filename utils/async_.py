from typing import Optional, Union, Callable, Coroutine, Any
import asyncio
import concurrent.futures
import aiohttp

def run_sync(coro: Coroutine):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, coro)
        concurrent.futures.wait([future])
        return future.result()

async def run_async(func: Callable):
    return await asyncio.get_event_loop().run_in_executor(None, func)
    

class AsyncTimer:
    def __init__(self, delay: Union[int, float], callback: Callable, *args, **kwargs):
        self._delay = delay
        self._callback = callback
        self._args = args
        self._kwargs = kwargs
        self._future = None

    async def _job(self):
        await asyncio.sleep(self._delay)
        if asyncio.iscoroutinefunction(self._callback):
            await self.callback(*self._args, **self._kwargs)
        else:
            self.callback(*self._args, **self._kwargs)
            

    def start(self):
        with concurrent.futures.ThreadPoolExecutor() as pool:
            self._future = pool.submit(run_sync, self._job())
        

    def cancel(self):
        if self._future is not None:
            self._future.cancel()
            self._future = None

    def is_running(self):
        return self._future is not None and not self._future.done()
    
    def callback(self, *args, **kwargs):
        self._callback(*args, **kwargs)
        self.cancel()
    
    def restart(self):
        self.cancel()
        self.start()



class AsyncRequests:
    @staticmethod
    async def get(url: str, params: Optional[dict] = None, data: Any = None, headers: Optional[dict] = None, cookies: Optional[dict] = None, auth: Optional[aiohttp.BasicAuth] = None, allow_redirects: bool = True, timeout: Optional[float] = None, json: Any = None, return_type: str = "json") -> Union[dict, str, bytes]: 
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, data=data, headers=headers, cookies=cookies, auth=auth, allow_redirects=allow_redirects, timeout=timeout, json=json) as response:
                response.raise_for_status()
                match return_type:
                    case "json":
                        return await response.json()
                    case "content":
                        return await response.content.read()
                    case _:
                        return await response.text()

    @staticmethod
    async def post(url: str, data: Any = None, json: Any = None, params: Optional[dict] = None, headers: Optional[dict] = None, cookies: Optional[dict] = None, auth: Optional[aiohttp.BasicAuth] = None, allow_redirects: bool = True, timeout: Optional[float] = None, return_type: str = "json") -> Union[dict, str, bytes]:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, json=json, params=params, headers=headers, cookies=cookies, auth=auth, allow_redirects=allow_redirects, timeout=timeout) as response:
                response.raise_for_status()
                match return_type:
                    case "json":
                        return await response.json()
                    case "content":
                        return await response.content.read()
                    case _:
                        return await response.text()
    
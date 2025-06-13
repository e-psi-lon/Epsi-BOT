from typing import Optional, Any, Literal, Union

import aiohttp


# noinspection PyProtectedMember
async def get(url: str, params: Optional[dict] = None, data: Any = None, headers: Optional[dict] = None,
              cookies: Optional[dict] = None, auth: Optional[aiohttp.BasicAuth] = None,
              allow_redirects: bool = True,
              timeout: aiohttp.ClientTimeout | aiohttp.helpers._SENTINEL | None = None, json: Any = None,
              return_type: Literal["json", "text", "content"] = "json") -> Union[dict, str, bytes]:
	"""
	Make a GET request

	Parameters
	----------
	url : str
		The URL to make the request to.
	params : Optional[dict]
		The parameters for the request. The default is None.
	data : Any
		The data for the request. The default is None.
	headers : Optional[dict]
		The headers for the request. The default is None.
	cookies : Optional[dict]
		The cookies for the request. The default is None.
	auth : Optional[aiohttp.BasicAuth]
		The authentication data for the request. The default is None.
	allow_redirects : bool
		Whether to allow redirects or not. The default is True.
	timeout : Optional[float]
		The timeout for the request. The default is None.
	json : Any
		The JSON data for the request. The default is None.
	return_type : Literal["json", "text", "content"]
		The type of the return value. The default is "json".

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

# noinspection PyProtectedMember
async def post(url: str, data: Any = None, json: Any = None, params: Optional[dict] = None,
               headers: Optional[dict] = None, cookies: Optional[dict] = None,
               auth: Optional[aiohttp.BasicAuth] = None, allow_redirects: bool = True,
               timeout: aiohttp.ClientTimeout | aiohttp.helpers._SENTINEL | None = None,
               return_type: Literal["json", "text", "content"] = "json") \
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
		The JSON data for the request. Default is None.
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
		The type of the return value. The default is "json".
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


# noinspection PyProtectedMember
async def head(url: str, params: Optional[dict] = None, headers: Optional[dict] = None,
		  cookies: Optional[dict] = None, auth: Optional[aiohttp.BasicAuth] = None,
		  allow_redirects: bool = True,
		  timeout: aiohttp.ClientTimeout | aiohttp.helpers._SENTINEL | None = None) -> dict:
	"""
	Make a HEAD request

	Parameters
	----------
	url : str
		The URL to make the request to.
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

	Returns
	-------
	dict
		The response headers of the request
	"""
	async with aiohttp.ClientSession() as session:
		async with session.head(url, params=params, headers=headers, cookies=cookies, auth=auth,
		                        allow_redirects=allow_redirects, timeout=timeout) as response:
			response.raise_for_status()
			return dict(response.headers)

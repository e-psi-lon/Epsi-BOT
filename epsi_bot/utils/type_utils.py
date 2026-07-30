from enum import Enum
from functools import lru_cache
from typing import Any, Literal, Union, cast, get_args, get_origin

import discord

__all__ = ["FfmpegFormats", "Sinks", "type_checking"]


class Sinks(Enum):
	"""Enum for the different types of audio sinks"""

	mp3 = discord.sinks.MP3Sink()
	wav = discord.sinks.WaveSink()
	ogg = discord.sinks.OGGSink()
	mp4 = discord.sinks.MP4Sink()


class FfmpegFormats(Enum):
	MP3 = ("-codec:a", "libmp3lame")
	FLAC = ("-codec:a", "flac", "-sample_fmt", "s16")
	OGG = ("-codec:a", "libvorbis")
	OPUS = ("-codec:a", "libopus")
	M4A = ("-codec:a", "aac")
	WAV = ("-codec:a", "pcm_s16le")


@lru_cache(maxsize=128)
def _format_type_name(type_hint: Any) -> str:
	"""Format type hint for readable error messages with caching for performance."""
	# noinspection PyProtectedMember
	if isinstance(type_hint, tuple):
		return " | ".join(_format_type_name(t) for t in type_hint)
	elif hasattr(type_hint, "__name__"):
		return type_hint.__name__
	elif hasattr(type_hint, "_name") and type_hint._name is not None:
		# Handle special typing constructs like typing.List
		# noinspection PyProtectedMember
		return type_hint._name
	else:
		return str(type_hint)


def _build_path(base_path: str, *parts: str) -> str:
	"""Build a dotted path from parts."""
	if not base_path:
		return ".".join(str(p) for p in parts if p)
	return ".".join([base_path] + [str(p) for p in parts if p])


def _parse_nested_key(key_to_split: str) -> list[str]:
	"""Parse nested key syntax: 'parent__child__attr' -> ['parent', 'child', 'attr']"""
	return key_to_split.split("__")


def _type_checking(
	value: Any,
	expected_type: type,
	*indexed: type,
	raise_error: bool = False,
	label: str = "value",
	keys: dict[Any, type] | None = None,
	use_attrs: bool = False,
	_parent_path: str = "",
	_depth: int = 0,
	**key_or_attrs: Any,
) -> bool:
	"""
	Internal function to check the type structure of a value comprehensively.
	Please refer to the `type_checking` function for the public interface and full documentation.
	"""
	# Add depth limit to prevent infinite recursion
	if _depth > 50:  # Arbitrary recursion limit
		if raise_error:
			raise RecursionError(
				f"Maximum recursion depth exceeded when checking {_build_path(_parent_path, label)}"
			)
		return False

	def _check_single_type(val: Any, expected: Any, path: str) -> bool:
		"""Check if a single value matches the expected type, with recursive support."""
		# Handle None values with Optional/Union[None, type]
		if val is None:
			# If the expected type is Optional or Union containing None
			origin = get_origin(expected)
			args = get_args(expected)

			if origin is Union and type(None) in args:
				return True

			if expected is type(None) or expected is None:
				return True

			if raise_error:
				raise TypeError(
					f"Expected {_format_type_name(expected)} for {path}, got None"
				)
			return False

		# Handle tuple of types (union)
		if isinstance(expected, tuple):
			return any(_check_single_type(val, t, path) for t in expected)

		# Handle Any type - always matches
		if expected is Any:
			return True

		# Handle Literal types
		origin = get_origin(expected)
		args = get_args(expected)
		if origin is Union and type(None) in args:
			return True  # Union with None is treated as Optional

		if origin is Literal:
			if val not in args:
				if raise_error:
					raise TypeError(f"Expected one of {args} for {path}, got {val}")
				return False
			return True

		# Handle generic types
		if origin is not None:
			# For generic types like list[str], dict[str, int], etc.
			if not isinstance(val, origin):
				if raise_error:
					raise TypeError(
						f"Expected {_format_type_name(expected)} for {path}, got {type(val).__name__}"
					)
				return False

			# Check generic arguments if present - RECURSIVE VALIDATION
			if args:
				if origin in (list, tuple, set, frozenset):
					# For sequences, recursively check all elements match the first type arg
					if hasattr(val, "__iter__"):
						for item_i, item in enumerate(val):
							item_path = f"{path}[{item_i}]"
							# Recursive call for nested structures
							if not _type_checking(
								item,
								args[0],
								raise_error=raise_error,
								label=item_path,
								_parent_path=item_path,
								_depth=_depth + 1,
							):
								return False
				elif origin is dict and len(args) >= 2:
					# For dicts, recursively check key and value types
					for k, v in val.items():
						key_path = f"{path} key {k!r}"
						value_path = f"{path}[{k!r}]"

						# Recursive validation for dict keys and values
						if not _type_checking(
							k,
							args[0],
							raise_error=raise_error,
							label=key_path,
							_parent_path=key_path,
							_depth=_depth + 1,
						):
							return False
						if not _type_checking(
							v,
							args[1],
							raise_error=raise_error,
							label=value_path,
							_parent_path=value_path,
							_depth=_depth + 1,
						):
							return False
			return True

		# Handle regular types
		if not isinstance(val, expected):
			if raise_error:
				raise TypeError(
					f"Expected {_format_type_name(expected)} for {path}, got {type(val).__name__}"
				)
			return False

		return True

	# Build current path
	current_path = _build_path(_parent_path, label) if _parent_path else label

	# Main type check
	if not _check_single_type(value, expected_type, current_path):
		return False

	# Check indexed values (*args) with recursive support
	if indexed:
		if not hasattr(value, "__getitem__") or not hasattr(value, "__len__"):
			if raise_error:
				raise TypeError(
					f"Cannot check indexed values on type {type(value).__name__} for {current_path}"
				)
			return False

		if len(value) < len(indexed):
			if raise_error:
				raise TypeError(
					f"Expected at least {len(indexed)} items in {current_path}, got {len(value)}"
				)
			return False

		for i, expected_item_type in enumerate(indexed):
			try:
				item_value = value[i]

				# Recursive validation for indexed items
				if not _type_checking(
					item_value,
					expected_item_type,
					raise_error=raise_error,
					label=f"[{i}]",
					_parent_path=current_path,
					_depth=_depth + 1,
				):
					return False
			except (IndexError, TypeError) as e:
				if raise_error:
					raise TypeError(f"Cannot access index {i} in {current_path}") from e
				return False

	# Process nested kwargs and combine with explicit keys
	all_keys = {}
	if keys is not None:
		all_keys.update(keys)

	# Process **kwargs with nested syntax support
	if not use_attrs:
		# Process **kwargs for dictionary keys
		nested_keys: dict[str, dict[str, type]] = {}
		for key, attr_expected_type in key_or_attrs.items():
			path_parts = _parse_nested_key(key)
			if len(path_parts) == 1:
				# Simple key
				all_keys[key] = attr_expected_type
			else:
				# Nested key: parent__child__attr
				# Store for recursive processing
				if path_parts[0] not in nested_keys:
					nested_keys[path_parts[0]] = {}
				nested_path = "__".join(path_parts[1:])
				nested_keys[path_parts[0]][nested_path] = attr_expected_type

		# Check direct keys
		if all_keys:
			if not hasattr(value, "__getitem__"):
				if raise_error:
					raise TypeError(
						f"Cannot check keys on non-subscriptable type {type(value).__name__} for {current_path}"
					)
				return False

			for key, expected_key_type in all_keys.items():
				try:
					key_value = value[key]

					# Recursive validation for key values
					if not _type_checking(
						key_value,
						expected_key_type,
						raise_error=raise_error,
						label=f"[{key!r}]",
						_parent_path=current_path,
						_depth=_depth + 1,
					):
						return False
				except (KeyError, TypeError, IndexError) as e:
					if raise_error:
						raise TypeError(
							f"Missing or invalid key {key!r} in {current_path}"
						) from e
					return False

		# Check nested keys recursively
		for parent_key, nested_checks in nested_keys.items():
			try:
				parent_value = value[parent_key]

				# Recursive call for nested structure
				if not _type_checking(
					parent_value,
					type(parent_value),  # Accept whatever type it is
					raise_error=raise_error,
					label=f"[{parent_key!r}]",
					_parent_path=current_path,
					use_attrs=False,
					_depth=_depth + 1,
					keys=cast(dict[Any, type], nested_checks),
				):
					return False
			except (KeyError, TypeError, IndexError) as e:
				if raise_error:
					raise TypeError(
						f"Missing or invalid key {parent_key!r} in {current_path}"
					) from e
				return False

	# Check object attributes (**kwargs when use_attrs=True) with nested support
	if use_attrs and key_or_attrs:
		# Process nested attributes
		nested_attrs: dict[str, dict[str, type]] = {}
		direct_attrs: dict[str, type] = {}

		for attr_key, attr_expected_type in key_or_attrs.items():
			path_parts = _parse_nested_key(attr_key)
			if len(path_parts) == 1:
				# Simple attribute
				direct_attrs[attr_key] = attr_expected_type
			else:
				# Nested attribute: parent__child__attr
				if path_parts[0] not in nested_attrs:
					nested_attrs[path_parts[0]] = {}
				nested_path = "__".join(path_parts[1:])
				nested_attrs[path_parts[0]][nested_path] = attr_expected_type

		# Check direct attributes
		for attr_name, expected_attr_type in direct_attrs.items():
			try:
				attr_value = getattr(value, attr_name)

				# Recursive validation for attribute values
				if not _type_checking(
					attr_value,
					expected_attr_type,
					raise_error=raise_error,
					label=attr_name,
					_parent_path=current_path,
					_depth=_depth + 1,
				):
					return False
			except AttributeError as e:
				if raise_error:
					raise TypeError(
						f"Missing attribute {attr_name} in {current_path}"
					) from e
				return False

		# Check nested attributes recursively
		for parent_attr, nested_checks in nested_attrs.items():
			try:
				parent_value = getattr(value, parent_attr)

				# Recursive call for nested attribute structure
				if not _type_checking(
					parent_value,
					type(parent_value),  # Accept whatever type it is
					raise_error=raise_error,
					label=parent_attr,
					_parent_path=current_path,
					use_attrs=True,
					_depth=_depth + 1,
					keys=cast(dict[Any, type], nested_checks),
				):
					return False
			except AttributeError as e:
				if raise_error:
					raise TypeError(
						f"Missing attribute {parent_attr} in {current_path}"
					) from e
				return False

	return True


def type_checking(
	value: Any,
	expected_type: Any,
	*indexed: Any,
	raise_error: bool = False,
	label: str = "value",
	keys: dict[Any, Any] | None = None,
	use_attrs: bool = False,
	**key_or_attrs: Any,
) -> bool:
	"""
	Check the type structure of a value comprehensively with recursive support.

	Parameters
	----------
	value : Any
	        The value to check
	expected_type : Any
	        The expected type (can be a type, generic type, or tuple of types)
	        Supports recursive generic types like list[dict[str, int]]
	        Supports Optional, Union, and Literal types
	*indexed : Any
	        Expected types for indexed positions (0, 1, 2, ...)
	        Supports recursive validation of nested structures
	raise_error : bool, default False
	        Whether to raise TypeError on mismatch
	label : str, default "value"
	        Label for error messages
	keys : dict[Any, Any] | None, default None
	        Expected types for dictionary keys: {key: expected_type}
	use_attrs : bool, default False
	        If True, **key_or_attrs are treated as object attributes
	        If False, **key_or_attrs are treated as dictionary keys
	**key_or_attrs : Any
	        Expected types for keys/attributes with nested support:
	        - Simple: name=str, age=int
	        - Nested: profile__age=int, settings__theme__color=str
	        - Recursive validation automatically applied to nested structures

	Returns
	-------
	bool
	        `True` if all checks pass, `False` otherwise
	"""
	try:
		return _type_checking(
			value,
			expected_type,
			*indexed,
			raise_error=raise_error,
			label=label,
			keys=keys,
			use_attrs=use_attrs,
			_parent_path="",
			_depth=0,
			**key_or_attrs,
		)
	except RecursionError:
		if raise_error:
			raise
		return False

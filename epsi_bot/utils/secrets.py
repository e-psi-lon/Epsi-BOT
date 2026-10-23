import os


def get_secret(name: str) -> str:
	"""Get a secret from /run/secrets (in snake_case) and fall back to environment variables (in SCREAMING_SNAKE_CASE)."""
	try:
		with open(f"/run/secrets/{name.lower()}", "r") as f:
			value = f.read().strip()
			if value:
				return f.read().strip()
	except FileNotFoundError:
		pass

	value = os.getenv(name.upper()) or ""
	if not value:
		raise ValueError(
			f"Secret '{name}' not found in /run/secrets or environment variables."
		)
	return value

# Music-BOT

Changing the line 287 of [cipher.py](./.venv/Lib/site-packages/pytube/cipher.py#287) to
```py
r'var {nfunc}\\s*=\\s*(\\[.+?])'.format(
```
is necessary for the bot to work.
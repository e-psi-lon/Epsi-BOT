# Music-BOT

## Format de sauvegarde des infos

Tout est dans une base de données sqlite3, dans le fichier [`database/database.db`](database/database.db) (non présent
sur le repo, mais créé automatiquement s'il n'existe pas).
Il y a 7 tables :

- `SERVER` qui contient les infos des guilds et qui se présente sous la forme suivante :

  | Colonne    | Type    |
  |------------|---------|
  | __id__     | INT     |
  | loop_song  | BOOLEAN |
  | loop_queue | BOOLEAN |
  | random     | BOOLEAN |
  | volume     | INT     |
  | position   | INT     |

- `SONG` qui contient les informations des chansons :

  | Colonne | Type         |
  |---------|--------------|
  | __id__  | INT          |
  | name    | VARCHAR(255) |
  | url     | TEXT         |

- `PLAYLIST` qui contient les informations des playlists :

  | Colonne       | Type         |
  |---------------|--------------|
  | __id__        | INT          |
  | name          | VARCHAR(255) |

- `ASKER` qui contient les informations des utilisateurs :

  | Colonne    | Type |
  |------------|------|
  | __id__     | INT  |
  | discord_id | INT  |

- `PLAYLIST_SONG` qui contient les informations des chansons dans les playlists :

  | Colonne           | Type |
  |-------------------|------|
  | # __playlist_id__ | INT  |
  | # __song_id__     | INT  |
  | position          | INT  |
  | asker             | INT  |

- `SERVER_PLAYLIST` qui contient les informations des playlists dans les guilds :

  | Colonne           | Type |
  |-------------------|------|
  | # __server_id__   | INT  |
  | # __playlist_id__ | INT  | 

- `QUEUE` qui contient les informations de la file d'attente des chansons :

  | Colonne         | Type         |
  |-----------------|--------------|
  | # __server_id__ | INT          |
  | # __song_id__   | INT          |
  | # asker_id      | INT          |
  | position        | INT          |



## Contributeurs

[![Contributeurs (vu que la repo est privée ça fonctionne pas bien)](https://contrib.rocks/image?repo=e-psi-lon/Music-BOT)](https://github.com/e-psi-lon/Music-BOT/graphs/contributors)

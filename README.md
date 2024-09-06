# Epsi-BOT

## Format de sauvegarde des infos

Tout est dans une base de données sqlite3, dans le fichier [`database/database.db`](database/database.db) (non présent
sur le repo, mais créé automatiquement s'il n'existe pas).
Il y a 8 tables :

- `SERVER` qui contient les infos des guilds et qui se présente sous la forme suivante :

  | Colonne    | Type    |
  |------------|---------|
  | __id__     | INTEGER |
  | loop_song  | BOOLEAN |
  | loop_queue | BOOLEAN |
  | random     | BOOLEAN |
  | volume     | INTEGER |
  | position   | INTEGER |

- `SONG` qui contient les informations des chansons :

  | Colonne | Type         |
  |---------|--------------|
  | __id__  | INTEGER      |
  | name    | VARCHAR(255) |
  | url     | TEXT         |

- `PLAYLIST` qui contient les informations des playlists :

  | Colonne       | Type         |
  |---------------|--------------|
  | __id__        | INTEGER      |
  | name          | VARCHAR(255) |

- `ASKER` qui contient les informations des utilisateurs :

  | Colonne    | Type    |
    |------------|---------|
  | __id__     | INTEGER |
  | discord_id | INTEGER |

- `PLAYLIST_SONG` qui contient les informations des chansons dans les playlists :

  | Colonne           | Type     |
  |-------------------|----------|
  | # __playlist_id__ | INTEGER  |
  | # __song_id__     | INTEGER  |
  | position          | INTEGER  |
  | asker             | INTEGER  |

- `SERVER_PLAYLIST` qui contient les informations des playlists dans les guilds :

  | Colonne           | Type     |
  |-------------------|----------|
  | # __server_id__   | INTEGER  |
  | # __playlist_id__ | INTEGER  |

- `USER_PLAYLIST` qui contient les informations des playlists dans les guilds :

  | Colonne           | Type     |
  |-------------------|----------|
  | # __user_id__     | INTEGER  |
  | # __playlist_id__ | INTEGER  |

- `QUEUE` qui contient les informations de la file d'attente des chansons :

  | Colonne         | Type         |
  |-----------------|--------------|
  | # __server_id__ | INTEGER      |
  | # __song_id__   | INTEGER      |
  | # asker_id      | INTEGER      |
  | position        | INTEGER      |

## Contributeurs

[![Contributeurs](https://contrib.rocks/image?repo=e-psi-lon/Epsi-BOT)](https://github.com/e-psi-lon/Epsi-BOT/graphs/contributors)

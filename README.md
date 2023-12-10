# Music-BOT

## Format de sauvegarde des infos

Tout est dans une base de données sqlite3, dans le fichier [`database/database.db`](database/database.db) (non présent
sur le repo, mais créé automatiquement s'il n'existe pas).
Il y a 4 tables:

- `SERVER` qui contient les infos des guilds et qui se présente sous la forme suivante:

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
  | title   | VARCHAR(255) |
  | url     | TEXT         |
  | asker   | VARCHAR(255) |

- `QUEUE` qui contient les informations de la file d'attente des chansons :

  | Colonne        | Type |
      |----------------|------|
  | __song_id__ #  | INT  |
  | __server_id__ #| INT  |
  | position       | INT  |

- `PLAYLIST` qui contient les informations des playlists :

  | Colonne         | Type         |
      |-----------------|--------------|
  | name            | VARCHAR(255) |
  | __server_id__ # | INT          |
  | __song_id__ #   | INT          |
  | position        | INT          |

## Contributeurs

<a href = "https://github.com/e-psi-lon/Music-BOT/graphs/contributors">
  <img src = "https://contrib.rocks/image?repo=e-psi-lon/Music-BOT"/> (la repo est privée donc je sais pas si ça affiche)
</a>

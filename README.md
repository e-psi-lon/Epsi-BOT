# Music-BOT

## Format de sauvegarde des infos

Tout est dans une base de données sqlite3, dans le fichier [`database/database.db`](database/database.db) (non présent sur le repo, mais créé automatiquement si il n'existe pas).
Il y a 4 tables:

- `SERVER` qui contient les infos des guilds et qui se présente sous la forme suivante:

    | Colonne    | Type    |
    |------------|---------|
    | id         | INT     |
    | loop_song  | BOOLEAN |
    | loop_queue | BOOLEAN |
    | random     | BOOLEAN |
    | volume     | INT     |
    | position   | INT     |

- `SONG` qui contient les informations des chansons :

    | Colonne | Type         |
    |---------|--------------|
    | id      | INT          |
    | title   | VARCHAR(255) |
    | url     | TEXT         |
    | asker   | VARCHAR(255) |

- `QUEUE` qui contient les informations de la file d'attente des chansons :

    | Colonne   | Type |
    |-----------|------|
    | song_id   | INT  |
    | server_id | INT  |
    | position  | INT  |

- `PLAYLIST` qui contient les informations des playlists :

    | Colonne   | Type         |
    |-----------|--------------|
    | name      | VARCHAR(255) |
    | server_id | INT          |
    | song_id   | INT          |
    | position  | INT          |

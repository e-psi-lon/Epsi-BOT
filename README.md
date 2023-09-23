# Music-BOT

Installer [ffmpeg](https://ffmpeg.org/download.html) est nécessaire pour que le bot fonctionne (Si j'y penses, je le mettrais dans la repo github)

## Format de sauvegarde des infos

Les infos sont sauvegardées dans un fichier dans le dossier [queue](./queue/) dont le nom est `<guild_id>.json`
Les fichiers se présentent sous la forme

```json
{
    "channel": 551515454515, // salon dans lequel le bot est connecte, type int ou null
    "loop-song": false, // true si la chanson en cours de lecture doit être répétée, type bool
    "loop-queue": false, // true si la file d'attente doit être répétée, type bool
    "random": false, // true si la file d'attente doit être jouée dans un ordre aléatoire, type bool
    "index": 0, // index de la chanson en cours de lecture dans la file d'attente, type int
    "queue": [ // file d'attente des chansons, type list
        {
            "title": "", // titre de la chanson, type str
            "url": "https://www.youtube.com/watch?v=...", // url de la chanson, type str
            "asker": 95884548745, // id de l'utilisateur qui a demandé la chanson, type int
            "file": "cache/nom de la video" // chemin vers le fichier audio de la chanson, type str. 
        }
    ],
    "playlist": { // Playlists enregistrées dans le serveur, type dict
        "Exemple": [ // nom de la playlist et liste des chansons, type list
            {
                "title": "", // titre de la chanson, type str
                "url": "https://www.youtube.com/watch?v=...", // url de la chanson, type str
                "asker": 95884548745, // id de l'utilisateur qui a demandé la chanson, type int
            }
        ]
    }
}
```

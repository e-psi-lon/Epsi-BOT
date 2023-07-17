# Music-BOT

Changer la ligne 287 de [cipher.py](./.venv/Lib/site-packages/pytube/cipher.py#287) pour
```py
r'var {nfunc}\\s*=\\s*(\\[.+?])'.format(
```
et installer ffmpeg sont nécessaires pour que le bot fonctionne


# Format de sauvegarde des infos

Les infos sont sauvegardées dans un fichier dans le dossier [queue](./queue/) dont le nom est <guild_id>.json
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
            "file": "audio/nom de la video" // chemin vers le fichier audio de la chanson, type str. 
            //Devrait bientot etre supprime car remplace par directement le flux audio
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
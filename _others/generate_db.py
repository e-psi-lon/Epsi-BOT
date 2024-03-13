import sqlite3

conn = sqlite3.connect("../database/database.db")
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS SERVER (
        server_id INTEGER,
        loop_song BOOLEAN,
        loop_queue BOOLEAN,
        random BOOLEAN,
        volume INTEGER,
        position INTEGER,
        PRIMARY KEY (server_id)
    );
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS SONG (
    song_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255),
    url TEXT
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS ASKER (
    asker_id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id INTEGER
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS PLAYLIST (
    playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255)
);
''')


cursor.execute('''
CREATE TABLE IF NOT EXISTS QUEUE (
    server_id INTEGER,
    song_id INTEGER,
    position INTEGER,
    asker INTEGER,
    FOREIGN KEY (server_id) REFERENCES SERVER(server_id),
    FOREIGN KEY (song_id) REFERENCES SONG(song_id),
    FOREIGN KEY (asker) REFERENCES ASKER(asker_id)
);
''')


cursor.execute('''
CREATE TABLE IF NOT EXISTS PLAYLIST_SONG (
    playlist_id INTEGER,
    song_id INTEGER,
    position INTEGER,
    asker INTEGER,
    FOREIGN KEY (asker) REFERENCES ASKER(asker_id),
    FOREIGN KEY (playlist_id) REFERENCES PLAYLIST(playlist_id),
    FOREIGN KEY (song_id) REFERENCES SONG(song_id)
    
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS SERVER_PLAYLIST (
    server_id INTEGER,
    playlist_id INTEGER,
    FOREIGN KEY (server_id) REFERENCES SERVER(server_id),
    FOREIGN KEY (playlist_id) REFERENCES PLAYLIST(playlist_id)
);
''')


conn.commit()
conn.close()

import sqlite3

conn = sqlite3.connect("../database/database.db")
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS SERVER (
        id INT,
        loop_song BOOLEAN,
        loop_queue BOOLEAN,
        random BOOLEAN,
        volume INT,
        position INT,
        PRIMARY KEY (id)
    );
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS SONG (
    id INT,
    name VARCHAR(255),
    url TEXT,
    PRIMARY KEY (id)
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS ASKER (
    id INT,
    discord_id INT,
    PRIMARY KEY (id)
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS PLAYLIST (
    id INT,
    name VARCHAR(255),
    PRIMARY KEY (id)
);
''')


cursor.execute('''
CREATE TABLE IF NOT EXISTS QUEUE (
    server_id INT,
    song_id INT,
    position INT,
    asker INT,
    FOREIGN KEY (server_id) REFERENCES SERVER(id),
    FOREIGN KEY (song_id) REFERENCES SONG(id),
    FOREIGN KEY (asker) REFERENCES ASKER(id)
);
''')


cursor.execute('''
CREATE TABLE IF NOT EXISTS PLAYLIST_SONG (
    playlist_id INT,
    song_id INT,
    position INT,
    asker INT,
    PRIMARY KEY (playlist_id, song_id),
    FOREIGN KEY (playlist_id) REFERENCES PLAYLIST(id),
    FOREIGN KEY (song_id) REFERENCES SONG(id),
    FOREIGN KEY (asker) REFERENCES ASKER(id)
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS SERVER_PLAYLIST (
    server_id INT,
    playlist_id INT,
    PRIMARY KEY (server_id, playlist_id),
    FOREIGN KEY (server_id) REFERENCES SERVER(id),
    FOREIGN KEY (playlist_id) REFERENCES PLAYLIST(id)
);
''')


conn.commit()
conn.close()

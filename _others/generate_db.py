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
    title VARCHAR(255),
    url TEXT,
    asker VARCHAR(255),
    PRIMARY KEY (id)
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS QUEUE (
    song_id INT,
    server_id INT,
    position INT,
    FOREIGN KEY (song_id) REFERENCES SONG(id)
    FOREIGN KEY (server_id) REFERENCES SERVER(id)
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS PLAYLIST (
    name VARCHAR(255),
    server_id INT,
    song_id INT,
    position INT,
    FOREIGN KEY (server_id) REFERENCES SERVER(id)
    FOREIGN KEY (song_id) REFERENCES SONG(id)
);
''')

conn.commit()
conn.close()

import sqlite3
import os


def format_table(table):
    # table est un dict avec comme clé le nom de la clé et comme valeur une liste des valeurs pour cette clé
    # On récupère les clés
    keys = list(table.keys())
    # On récupère la taille de chaque colonne
    sizes = []
    for key in keys:
        sizes.append(len(key))
        for value in table[key]:
            sizes[-1] = max(sizes[-1], len(str(value)))
    # On crée la ligne du haut
    line = "+"
    for size in sizes:
        line += "-" * (size + 2) + "+"
    # On crée la ligne des clés
    keys_line = "|"
    for i in range(len(keys)):
        keys_line += " " + keys[i] + " " * (sizes[i] - len(keys[i])) + " |"
    # On crée les lignes des valeurs
    values_lines = []
    for i in range(len(table[keys[0]])):
        values_lines.append("|")
        for j in range(len(keys)):
            values_lines[-1] += " " + str(table[keys[j]][i]) + " " * (sizes[j] - len(str(table[keys[j]][i]))) + " |"
    # On crée la ligne du bas
    bottom_line = "+"
    for size in sizes:
        bottom_line += "-" * (size + 2) + "+"
    # On crée le tableau
    table = line + "\n" + keys_line + "\n" + line + "\n"
    for values_line in values_lines:
        table += values_line + "\n"
    table += bottom_line
    return table


def check_db():
    # On récupère les tables
    conn = sqlite3.connect("database/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables : {', '.join([table[0] for table in tables])}")
    # On récupère les données de chaque table
    for table in tables:
        cursor.execute(f"SELECT * FROM {table[0]};")
        data = cursor.fetchall()
        print(f"\nTable {table[0]} :")
        # On prend les noms des clés
        cursor.execute(f"PRAGMA table_info({table[0]});")
        keys = cursor.fetchall()
        keys = [key[1] for key in keys]
        # On transforme le tout en dict
        table_dict = {}
        for key in keys:
            table_dict[key] = []
        for line in data:
            for i in range(len(keys)):
                table_dict[keys[i]].append(line[i])
        # On affiche le tableau
        print(format_table(table_dict))
    conn.close()


if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    check_db()
    input()

# import MySQLdb._exceptions
# import MySQLdb._mysql
# from myutils import DB_HOST, DB_USER, DB_PASSWORD, DB_PORT, DB_NAME
# from flask_mysqldb import MySQL
# from flask import Flask
# import MySQLdb.cursors

# mysql = None


# def init(app: Flask):
#     global mysql
#     app.config['MYSQL_HOST'] = DB_HOST
#     app.config['MYSQL_USER'] = DB_USER
#     app.config['MYSQL_PORT'] = 3306
#     app.config['MYSQL_PASSWORD'] = DB_PASSWORD
#     app.config['MYSQL_DB'] = DB_NAME
#     app.config["MYSQL_CURSORCLASS"] = "DictCursor"

#     print("DB", DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)

#     mysql = MySQL(app)
#     mysql.init_app(app)

#     print("MYSQL", mysql.connection, MySQLdb.apilevel)

#     return mysql


# def execute_query(query: str, params: tuple):
#     if not mysql:
#         raise Exception("MySQL Connection not initialized")

#     cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

#     cursor.execute(query, params)

#     return cursor


# def fetch_all(query: str, params: tuple):
#     cursor = execute_query(query, params)
#     return cursor.fetchall()


# def fetch_one(query: str, params: tuple):
#     cursor = execute_query(query, params)
#     return cursor.fetchone()


# def execute(query: str, params: tuple):
#     cursor = execute_query(query, params)
#     return cursor.lastrowid

print("mysql.py")

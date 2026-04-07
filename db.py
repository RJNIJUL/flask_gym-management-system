from flask_mysqldb import MySQL
from MySQLdb.cursors import DictCursor
mysql = MySQL()

def init_db(app):
    app.config["MYSQL_HOST"] = "localhost"
    app.config["MYSQL_USER"] = "root"
    app.config["MYSQL_PASSWORD"] = "abc@123"
    app.config["MYSQL_DB"] = "gym"
    app.config["MYSQL_CURSORCLASS"] = "DictCursor"

    mysql.init_app(app)

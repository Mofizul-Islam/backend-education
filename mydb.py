import psycopg2
import json
from myutils import DB_NAME, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_SCHEMA
import json

def get_db_connection():
    conn = psycopg2.connect(dbname = DB_NAME,
                            host = DB_HOST,
                            port = DB_PORT,
                            user = DB_USER,
                            password = DB_PASSWORD)
    conn.autocommit = True
    return conn
     
# parameters is a tuple
def run_select(query, parameters=None):
    conn = get_db_connection()
    cursr = conn.cursor()
    cursr.execute(query, parameters)
    rows = cursr.fetchall()
    cursr.close()
    conn.close
    return rows

# idu stands for insert/delete/update
def run_idu(query, parameters=None):
    conn = get_db_connection()
    cursr = conn.cursor()
    cursr.execute(query, parameters)
    rowcount = cursr.rowcount
    cursr.close()
    conn.close
    return rowcount

def run_idu_with_conn(conn, query, parameters=None):
    cursr = conn.cursor()
    cursr.execute(query, parameters)
    rowcount = cursr.rowcount
    cursr.close()
    return rowcount

def update_table_fields(tablename, 
                        fields_to_update,
                        values_to_update,
                        where_condition,
                        parameter_list
):
    s_set = ', '.join([f'{item}=%s' for item in fields_to_update])
    query = f'update {DB_SCHEMA}.{tablename} set {s_set} {where_condition}'
    return run_idu(query, tuple(values_to_update + parameter_list))

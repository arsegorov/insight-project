from datetime import datetime

missing = -1
succeeded = 0
failed = 1
processing = 2

xml_log_table = 'xml_log'
time_field, time_props = 'date_time_utc', 'timestamp without time zone'
file_field, file_props = 'file', 'text'
status_field, status_props = 'status', 'smallint'  # possible values: succeeded, failed, processing, other = -1
msgs_field, msgs_props = 'messages', 'text[] NOT NULL'
xml_log_pk = f'{time_field}'


def create_xml_log_table(connection):
    cur = connection.cursor()
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS {xml_log_table} ("
        f"{time_field} {time_props},"
        f"{file_field} {file_props},"
        f"{status_field} {status_props},"
        f"{msgs_field} {msgs_props},"
        f"PRIMARY KEY ({xml_log_pk}));")

    connection.commit()


def get_logger():
    logger = [datetime.utcnow(), []]

    def push_message(string):
        # debug: don't append if logger has 20 items
        if len(logger[1]) < 20:
            logger[1].append(f'{datetime.utcnow()}: {string}')

    return logger, push_message


def commit_log(logger, connection, filename=None, status=-1):
    create_xml_log_table(connection)

    cur = connection.cursor()
    log_lines = "ARRAY['" + "','".join(logger[1]) + "']"
    cur.execute(
        f"INSERT INTO {xml_log_table} ("
        f"{time_field}, {file_field}, {status_field}, {msgs_field}) "
        
        f"VALUES ("
        f"'{logger[0]}', '{filename}', {status}, {log_lines});")

    connection.commit()

    # Empty the local log after committing to the database
    logger[1] = []
    logger[0] = datetime.utcnow()

# simplify log
def log_msg(msg, connection, filename=None, status=-1):
    #create_xml_log_table(connection)
    time_stamp = datetime.utcnow()
    log_lines = "ARRAY['" + msg + "']"
    cur = connection.cursor()
    cur.execute(
        f"INSERT INTO {xml_log_table} ({time_field}, {file_field}, {status_field}, {msgs_field}) "
        f"VALUES ('{time_stamp}', '{filename}', {status}, {log_lines});"
        )

    connection.commit()
    cur.close()

# return txn id
def new_txn(connection, filename, begin_datetime):
    # detect duplicates
    cur = connection.cursor()
    cur.execute(f"""
        select id from xml_txns where filename = '{filename}';
    """)
    rows = cur.fetchall()
    if len(rows):
        return rows[0][0]

    cur.execute(f"""
        INSERT INTO xml_txns (filename, begin_datetime) 
        VALUES ('{filename}', '{begin_datetime}') 
        returning id;
    """)
    connection.commit()
    rows = cur.fetchall()
    cur.close()
    return rows[0][0]

def log_txn(connection, id, status, num_locations=0, msg=None):
    end_datetime = datetime.utcnow()
    cur = connection.cursor()
    cur.execute(f"""
        UPDATE xml_txns 
        SET 
            end_datetime='{end_datetime}' 
            ,status={status}
            ,num_locations={num_locations} 
            ,msg={msg}
        WHERE id = {id};
    """)
    connection.commit()
    cur.close()

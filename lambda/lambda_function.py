import os

import boto3
import psycopg2
from psycopg2.extras import execute_batch
from lazyreader import lazyread
import schemas
from datetime import datetime

#################
# Database stuff
#################

password = os.environ.get('PGPASSWORD')
meta_db = "'meta'"
rds_db_user = "'arsegorovDB'"
rds_host = "'metainstance.cagix2mfixd1.us-east-1.rds.amazonaws.com'"

connection = psycopg2.connect(f"dbname={meta_db} "
                              f"user={rds_db_user} "
                              f"host={rds_host} "
                              f"password='{password}'")
cur = connection.cursor()

############
# AWS stuff
############
s3 = boto3.resource('s3')


#######
# Main
#######
def main(event, context):
    """
    This Lambda's entry point

    :param event: the event received from the s3 bucket
    :param context: the runtime environment information
    """
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']

    obj = s3.Object(bucket_name, object_key)

    if object_key[-6:] == 'schema':
        body = obj.get()['Body']
        schema_json = body.read().decode('utf-8')
        schemas.process_schema(schema_json, connection)
        return 0

    if object_key[-3:] == 'csv':
        schema = schemas.find_schema(object_key, connection)
        if schema is None:
            print(f"An appropriate schema for the file {object_key} hasn't been found.")
            return 0

        tables = schema[2]
        body = obj.get()['Body']

        parse_record = {}
        write_to_db = {}
        batch = {}
        log = {}
        existing_pk_values = {}
        malformed_count = {}
        duplicates_count = {}

        for table in tables:
            tb_name = table['table']

            parse_record[tb_name], write_to_db[tb_name] = schemas.generate_data_processors(table, connection)

            batch[tb_name] = []
            log[tb_name] = []

            pk = ', '.join(table['primary_key'])
            cur.execute(f'SELECT {pk} FROM {tb_name};')
            rows = cur.fetchall()

            existing_pk_values[tb_name] = set(rows)
            malformed_count[tb_name] = 0
            duplicates_count[tb_name] = 0

        line_number = 0
        empty_lines = 0
        for line in lazyread(body, b'\n'):
            line_number += 1

            if len(line) == 0:
                empty_lines += 1
                continue

            fields = line.decode('utf-8').split(',')

            for table in tables:
                tb_name = table['table']

                try:
                    record = parse_record[tb_name](fields,
                                                   line_number,
                                                   lambda msg: log[tb_name].append(
                                                       (datetime.utcnow(), msg)
                                                   ),
                                                   existing_pk_values[tb_name],
                                                   tb_name)
                    if record is None:
                        malformed_count[tb_name] += 1
                    elif record == {}:
                        duplicates_count[tb_name] += 1
                    else:
                        batch[tb_name].append(record)

                except ValueError:
                    pass

                # When there are enough records in the buffer,
                # send the records as a batch, to reduce communication overhead
                if len(batch[tb_name]) == 100:
                    for t in tables:
                        name = t['table']
                        write_to_db[name](batch[name])
                        batch[name] = []

        for table in tables:
            tb_name = table['table']
            if len(batch[tb_name]) > 0:
                write_to_db[tb_name](batch[tb_name])
            skipped = malformed_count[tb_name] + empty_lines + duplicates_count[tb_name]

            log[tb_name].append(
                (datetime.utcnow(),
                 f'Total scanned lines: {line_number}\n'
                 f'Records inserted into table {tb_name}: {line_number - skipped}\n'
                 f'Skipped lines: {skipped} (incl. {empty_lines} blank, {malformed_count[tb_name]} malformed, '
                 f'{duplicates_count[tb_name]} duplicates)\n')
            )

            write_log(tb_name, log[tb_name])

        # connection.close()
        return 0


#
# The table for storing logs
#

logs_table = 'logs'
table_name_field, table_name_props = 'table_name', 'text'
timestamp_field, timestamp_props = 'timestamp_desc', 'timestamp'
message_field, message_props = 'message', 'text'


def create_logs_table():
    """
    Creates a table for storing logs.
    """
    cur.execute(f"CREATE TABLE IF NOT EXISTS {logs_table} ("
                f"{table_name_field} {table_name_props}, "
                f"{timestamp_field} {timestamp_props}, "
                f"{message_field} {message_props}, "
                f"PRIMARY KEY ({table_name_field}, {timestamp_field}));")

    connection.commit()


def write_log(tb_name, log):
    create_logs_table()

    execute_batch(
        cur,
        f'INSERT INTO {logs_table} ('
        f'{table_name_field}, {timestamp_field}, {message_field}'
        f') '
        f'VALUES ('
        f"'{tb_name}', %({timestamp_field})s, %({message_field})s"
        f');',
        [{f'{timestamp_field}': entry[0], f'{message_field}': entry[1]} for entry in log]
    )

    connection.commit()

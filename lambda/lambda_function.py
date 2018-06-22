import os

import boto3
import psycopg2
from lazyreader import lazyread
import schemas

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

        tables = schema[1]
        body = obj.get()['Body']

        parse_record = {}
        write_to_db = {}
        batch = {}

        for table in tables:
            tb_name = table['table']

            parse_record[tb_name], write_to_db[tb_name] = \
                schemas.generate_data_processors(table, connection)
            batch[tb_name] = []

        for line in lazyread(body, b'\n'):
            if len(line) == 0:
                continue

            fields = line.decode('utf-8').split(',')

            for table in tables:
                tb_name = table['table']
                try:
                    record = parse_record[tb_name](fields)
                    batch[tb_name].append(record)
                except ValueError:
                    pass

                # When there are enough records in the buffer,
                # send the records as a batch, to reduce communication overhead
                if len(batch[tb_name]) == 100:
                    write_to_db[tb_name](batch[tb_name])
                    batch[tb_name] = []

        for table in tables:
            tb_name = table['table']
            if len(batch[tb_name]) > 0:
                write_to_db[tb_name](batch[tb_name])

        # connection.close()
        return 0

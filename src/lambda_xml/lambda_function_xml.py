# test Jenkinsfile 
# case 1 - add this comment and deploy 
# resule : success

# case 2 - intentionally break by skipping extract_data


import os
import time
import boto3
from botocore.exceptions import ClientError
import psycopg2    
import json
import yaml
import decimal
from xml.etree.ElementTree import fromstring, ParseError
import gzip
import schemas_xml
from logs import new_txn, log_txn, log_msg, get_logger, commit_log, succeeded, failed, processing
from datetime import datetime

RETRY_EXCEPTIONS = ('ProvisionedThroughputExceededException',
                    'ThrottlingException')
                    
############
# AWS stuff
############

s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

#################
# Database stuff
#################

db_host = os.environ.get('AWS_PG_DB_HOST')
db_name = os.environ.get('AWS_PG_DB_NAME')
db_user = os.environ.get('AWS_PG_DB_USER')
password = os.environ.get('AWS_PG_DB_PASS')

db_connection_string = f"dbname='{db_name}' " + \
    f"user='{db_user}' " + \
    f"host='{db_host}' " + \
    f"password='{password}'"

connection = psycopg2.connect(db_connection_string)

traffic_table = dynamodb.Table('TrafficSpeed')

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if abs(o) % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def main(event, context):
    """
    This Lambda's entry point

    :param event: the event received from the s3 bucket
    :param context: the runtime environment information
    """
    print(event)


    logger, log = get_logger()  

    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']

    # open new transaction / get its id
    id_txn = new_txn(connection, object_key, datetime.utcnow())

    obj = s3.Object(bucket_name, object_key)

    # If the uploaded file is a schema, add it to the Postgres
    if object_key[-3:] == 'yml':

        log_msg('Requesting file from S3', connection, object_key, processing)

        try:
            body = obj.get()['Body']
            contents = body.read()
        except ClientError as ex:
            txn_msg = f'Error with S3: {ex.response["Error"]["Code"]}'
            log_msg(txn_msg, connection, object_key, failed)
            log_txn(connection, id_txn, failed, msg=txn_msg)
            return

        log_msg('Read contents from S3', connection, object_key, processing)

        try:
            schema = yaml.load(contents.decode('utf-8'))

            schemas_xml.add_schema(schema, connection)
            log_msg('Add schema to database', connection, object_key, processing)
        except:
            txn_msg = 'Error with processing schema'
            log_msg(txn_msg, connection, object_key, failed)
            log_txn(connection, id_txn, failed, txn_msg)
            return

        # schema added successfully
        txn_msg = 'Finished processing schema'
        log_msg(txn_msg,connection, object_key, succeeded)
        log_txn(connection, id_txn, succeeded, msg=txn_msg)

    # If the uploaded file is the actual data
    elif object_key[-3:] == 'xml' or object_key[-2:] == 'gz':
        log_msg('Read data from S3', connection, object_key, processing)

        # Read the contents of the file
        try:
            body = obj.get()['Body']
            contents = body.read()
        except ClientError as ex:
            txn_msg = f'Error with reading data: {ex.response["Error"]["Code"]}'
            log_msg(txn_msg, connection, object_key, failed)
            log_txn(connection, id_txn, failed, msg=txn_msg)
            return

        # for gzip-compressed files, decompress first
        if object_key[-2:] == 'gz':
            log_msg('Data in GZ format', connection, object_key, processing)
            try:
                contents = gzip.decompress(contents)
            except:
                txn_msg = "Error with decompressing .gz data"
                log_msg(txn_msg, connection, object_key, failed)
                log_txn(connection, id_txn, failed, msg=txn_msg)
                return

            log_msg('Decompressed data', connection, object_key, processing)

        print("DEBUG:\n",contents.decode('utf-8'))

        try:
            xml_data = fromstring(contents.decode('utf-8'))
        except ParseError:
            txn_msg = "Error with parsing XML data"
            log_msg(txn_msg, connection, object_key, failed)
            log_txn(connection, id_txn, failed, msg=txn_msg)
            return

        # Find the matching schema in the Postgres
        date = next(
            xml_data.iter('{http://datex2.eu/schema/2/2_0}publicationTime')
        ).text
        schema = schemas_xml.find_schema(object_key, date,
                                         connection)

        if schema is None:
            txn_msg = "Error with finding matching schema"
            log_msg(txn_msg, connection, object_key, failed)
            log_txn(connection, id_txn, failed, msg=txn_msg)
            return

        log_msg('Found matching schema in DB', connection, object_key, processing)

        # Load the schema
        try:
            xml_prefixes = schema[3]['prefixes']
            data_schema = schema[3]['data']
        except:
            txn_msg = 'Unexpected schema format'
            log_msg(txn_msg, connection, object_key, failed)
            log_txn(connection, id_txn, failed, msg=txn_msg)
            return

        log_msg("Start extracting data ...", connection, object_key, processing)

        # skip processing
        #return

        # Form the data to upload to Dynamo
        data = schemas_xml.extract_data(xml_data,
                          data_schema,
                          xml_prefixes,
                          log).popitem()[1]

        commit_log(logger, connection, object_key, processing)

        print("DEBUG:\n",data[0])
            

        size = len(data)
        log_msg(f'Writing {size} locations to DynamoDB', connection, object_key, processing)

        # Break the batch into reasonably sized chunks
        chunk_size = 200
        for i in range(0, size, chunk_size):
            if i >= 2*chunk_size :      # testing 2 chunks
                break
            j = min(size, i + chunk_size)


            with traffic_table.batch_writer(
                    overwrite_by_pkeys=['measurementSiteReference', 'measurementTimeDefault']
            ) as batch:
                for item in data[i:j]:
                    batch.put_item(Item=item)

            log_msg(f'Wrote items {i}-{j}', connection, object_key,processing)

        txn_msg = 'Finished processing traffic data'
        log_msg(txn_msg, connection, object_key, succeeded)
        log_txn(connection, id_txn, succeeded, num_locations=size, msg=txn_msg)    

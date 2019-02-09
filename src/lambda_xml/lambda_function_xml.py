BREAK_BUILD=False
# BREAK_BUILD=True
# intentionally break by skipping last log_txn call


import os
import time
import boto3
from botocore.exceptions import ClientError
import psycopg2    
import json
import yaml
#import decimal
from decimal import Decimal

# from xml.etree.ElementTree import fromstring, ParseError
try:
    import xml.etree.cElementTree as ET  #  accelerated C implementation
except ImportError:
    import xml.etree.ElementTree as ET

import gzip
import schemas_xml
from logs import new_txn, log_txn, log_msg, get_logger, commit_log, succeeded, failed, processing
from datetime import datetime

RETRY_EXCEPTIONS = ('ProvisionedThroughputExceededException',
                    'ThrottlingException')
FLAG_DEBUG = True
NS_PREFIX = '{http://datex2.eu/schema/2/2_0}'

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

db_connection_string = f"dbname='{db_name}' user='{db_user}' host='{db_host}' password='{password}'"

connection = psycopg2.connect(db_connection_string)

traffic_table = dynamodb.Table('TrafficSpeed')

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            if abs(o) % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

# parse traffic data tree and extract data for DynamoDB
def extract_traffic_data(tree, ns_prefix=None, flag_debug=False):
    site_data = []
    for site in tree.iter(tag=f'{ns_prefix}siteMeasurements'):
        measure_dic = {}

        for elem in site.iter(tag=f'{ns_prefix}measurementSiteReference'):   # iter over a given node with  tag
            if flag_debug: print(elem.tag, elem.attrib)
            measure_dic["measurementSiteReference"] = elem.attrib['id']
            break 

        for elem in site.iter(tag=f'{ns_prefix}measurementTimeDefault'):   # iter over a given node with  tag
            if flag_debug: print(elem.tag, elem.attrib, elem.text)
            measure_dic["measurementTimeDefault"] = elem.text
            break

        basic_data = []
        for elem in site.iter(tag=f'{ns_prefix}measuredValue'):
            data_dic = {}
            if flag_debug: print("par: ", elem.tag,elem.attrib)
            if elem.attrib and 'index' in elem.attrib:
                data_dic["Channel"] = elem.attrib['index']
            for el in elem.iter():
                if flag_debug: print("ch: ", el.tag,el.attrib,el.text)
                if "Channel" not in data_dic: continue
                if el.tag==f'{ns_prefix}speed':
                    data_dic["Type"] = 'TrafficSpeed'
                    data_dic["Speed"] = Decimal(f'{el.text}')
                    break
                elif el.tag==f'{ns_prefix}vehicleFlowRate':
                    data_dic["Type"] = 'TrafficFlow'
                    data_dic["Flow"] = Decimal(f'{el.text}')
                    break
            if data_dic:
                basic_data.append(data_dic)

        measure_dic["ns1:measuredValue"] = basic_data

        site_data.append(measure_dic)
    return site_data

def main(event, context):
    """
    This Lambda's entry point

    :param event: the event received from the s3 bucket
    :param context: the runtime environment information
    """
    print(event)

    # rewritten
    # logger, log = get_logger()  

    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']

    # open new transaction / get its id
    id_txn = new_txn(connection, object_key, datetime.utcnow())
    if id_txn < 0:
        log_msg('Same file being processed now ...', connection, object_key, processing)
        return

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

        log_msg("Start extracting data ...", connection, object_key, processing)
        try:
            xml_data = ET.fromstring(contents.decode('utf-8'))
        except ET.ParseError as ex:
            txn_msg = f'Error with parsing XML data: {ex.response["Error"]["Code"]}'
            log_msg(txn_msg, connection, object_key, failed)
            log_txn(connection, id_txn, failed, msg=txn_msg)
            return

        data = extract_traffic_data(xml_data, NS_PREFIX)

        # print("DEBUG:\n",data[0])

        size = len(data)
        log_msg(f'Writing {size} locations to DynamoDB', connection, object_key, processing)

        # Break the batch into reasonably sized chunks
        chunk_size = 200
        for i in range(0, size, chunk_size):
            # processing only subset when debugging
            if FLAG_DEBUG and i > 2*chunk_size :  
                break

            j = min(size, i + chunk_size)


            with traffic_table.batch_writer(
                    overwrite_by_pkeys=['measurementSiteReference', 'measurementTimeDefault']
            ) as batch:
                for item in data[i:j]:
                    batch.put_item(Item=item)

            log_msg(f'Wrote items {i}-{j}', connection, object_key,processing)

        # break build by skipping this
        if BREAK_BUILD: 
            return

        txn_msg = 'Finished processing traffic data'
        log_msg(txn_msg, connection, object_key, succeeded)
        log_txn(connection, id_txn, succeeded, num_locations=size, msg=txn_msg) 

        # delete processed file
        s3.Object(bucket_name,object_key).delete()

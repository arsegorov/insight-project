import os
import boto3
import psycopg2
import json
import yaml
import decimal
import xml.etree.ElementTree as ET
import time
import schemas_xml

############
# AWS stuff
############
s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

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
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']

    obj = s3.Object(bucket_name, object_key)

    if object_key[-3:] == 'yml':
        body = obj.get()['Body']
        schema = yaml.load(body.read().decode('utf-8'))
        schemas_xml.add_schema(schema, connection)

    elif object_key[-3:] == 'xml':
        t = time.time()

        body = obj.get()['Body'].read().decode('utf-8')
        xml_data = ET.fromstring(body)

        schema = schemas_xml.find_schema(object_key,connection)

        prefix = schema[3]['prefixes']
        data_schema = schema[3]['data']

        data = schemas_xml \
            .extract_data(xml_data,
                          data_schema,
                          prefix,
                          lambda x: 1) \
            .popitem()[1]

        size = len(data)
        for i in range(0, size, 500):
            j = min(size, i + 500)
            with traffic_table \
                    .batch_writer(overwrite_by_pkeys=['measurementSiteReference', 'measurementTimeDefault']) as batch:
                for item in data[i:j]:
                    # batch.delete_item(Key={
                    #     'measurementSiteReference': item['measurementSiteReference'],
                    #     'measurementTimeDefault': item['measurementTimeDefault']
                    # })
                    batch.put_item(Item=item)

            print(f'Items put: {i}-{j}\n'
                  f'Elapsed time: {time.time() - t}')

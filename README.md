# Data Freeway
_Making traffic data clean and accessible_

## Motivation
I've been interested in services that would collect traffic data
at a large scale, to provide customers with insights about
business costs related to transportation.

To be able to provide such services, fast access to a large amount
of historical and real-time data is necessary.

![Map of the Netherlands traffic sensors network][sensorsMap]

In the Netherlands, they have a
[network of sensors](http://www.ndw.nu/)
across the entire country,
at most major intersections and interchanges.
The readings from over 100,000 speed and flow
sensors are reported every minute,
which creates an exciting opportunity
for analysis. The collected data goes back to at least 2011!

However, the historical data, despite being free for anyone to use,
is difficult to get by,
primarily because of a limited system throughput.
One can [request data](http://83.247.110.3/OpenDataHistorie/)
only from a contiguous period of time,
which is at most about a week long.
The request has to be filed manually,
and takes minutes to hours or even days to fulfill before
the data can be even downloaded.

### Problems with XML
Currently, the data are stored in an XML format, which is
notoriously verbose. It could take about 400 bytes to store just 1 sensor reading!
```xml
<!--Linebreaks and indents added for readability-->
<ns1:siteMeasurements>
    <ns1:measurementSiteReference id="PZH01_MST_0690_00" targetClass="MeasurementSiteRecord"
                                  version="1"/>
    <ns1:measurementTimeDefault>2017-12-31T22:59:00Z</ns1:measurementTimeDefault>
    <ns1:measuredValue index="1">
        <ns1:measuredValue>
            <ns1:basicData xsi:type="TrafficFlow">
                <ns1:vehicleFlow>
                    <ns1:vehicleFlowRate>60</ns1:vehicleFlowRate>
                </ns1:vehicleFlow>
            </ns1:basicData>
        </ns1:measuredValue>
    </ns1:measuredValue>
</ns1:siteMeasurements>
```
Also, the schema for the data has evolved,
and analyzing it using the same queries might not work every time.

## Goals
My project aims to make the data more readily available
to the customers. I tried to improve storing of the data storage
on two parameters:
* uniformity of the schema, by filtering only the necessary
components of the data
* availability, by saving the processed data to
a distributed, low-latency storage

In addition to these primary goals, cleaning the data by keeping
only the pieces that are needed would reduce the volume used for storage.

## The Pipeline

![pipeline]

The schemas and source files are put into an S3 bucket from where
they are ingested into a Lambda function. Depending on whether
the file is a schema or a data file, the Lambda function will
either:
* store the schema to a Postgres database on RDS, or
* find the appropriate schema in the Postgres, based on the data file's
publication date, and then extract the pieces of data specified in the schema.
The yielded records are then put into a DynamoDB table,
and the logging and job status information are recorded in the Postgres

A frontend running on Flask displays which files have been processed for a given date.

### Challenges

#### Schema Updates
XML might be convenient in that it allows an open-ended schema,
but that also posed one of the challenges, as the schema would
sometimes change between different data files.

A solution to this challenge was to not to pay too much attention
to the nesting depths between ancestor/descendant nodes in the XML.

#### Describing What to Search For
The next challenge after deciding upon which
pieces of information are needed,
was choosing both a machine- and human-readable format
for describing these pieces.

I decided to use YAML, which I found to be rather succinct and
reasonably easy to learn, to author, and to understand.

Since the YAML file
is describing XML nodes and attributes, I also found it natural to use
XPATH in the schema files, which would make traversing XML possible
without having to translate search paths into Python expressions.

In the end, the structure of the YAML schema would describe the structure of the produced records,
whereas XPATH would refer to the structure of the XML.

```yaml
meta:
  files: '%Trafficspeed.xml'
  version: '2018-06-26T23:13:00Z'
  description: 'Data from traffic speed and flow sensors, source - NDW, the Netherlands'
processing:
  prefixes:
    xsi: 'http://www.w3.org/2001/XMLSchema-instance'
    ns0: 'http://schemas.xmlsoap.org/soap/envelope/'
    ns1: 'http://datex2.eu/schema/2/2_0'
  data:
    ns1.siteMeasurements[]:
      ns1.measurementSiteReference: _.id, str, measurementSiteReference
      ns1.measurementTimeDefault: text, timestamp, measurementTimeDefault
      ns1.measuredValue[]:
      - _: '.[@index]'
        _.index: int, Channel
        ns1.basicData:
        - _: '.[@xsi:type="TrafficFlow"]'
          _.xsi.type: text, Type
          ns1.vehicleFlowRate: text, float, Flow
        - _: '.[@xsi:type="TrafficSpeed"]'
          _.xsi.type: text, Type
          ns1.averageVehicleSpeed:
            _.numberOfInputValuesUsed: int, InputSize
            ns1.speed: text, float, Speed
```

[sensorsMap]: images/map_small.png
[pipeline]: images/pipeline.png
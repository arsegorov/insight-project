import json
from datetime import datetime
from decimal import Decimal

#
# The table for storing known schemas
#

xml_schemas_table = 'xml_schemas'
file_pattern_field, file_pattern_props = 'file_pattern', 'text'
schema_time_field, schema_time_props = 'schema_datetime_utc', 'timestamp'
schema_desc_field, schema_desc_props = 'schema_description', 'text'
proc_schema_field, proc_schema_props = 'processing_schema', 'json NOT NULL'
xml_schemas_pk = f'{file_pattern_field}, {schema_time_field}'


def create_schemas_meta_table(connection):
    """
    Creates a meta info table for storing known schemas.

    :param connection: a connection to the database
    """
    cur = connection.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {xml_schemas_table} ("
                f"{file_pattern_field} {file_pattern_props},"
                f"{schema_time_field} {schema_time_props},"
                f"{schema_desc_field} {schema_desc_props},"
                f"{proc_schema_field} {proc_schema_props},"
                f"PRIMARY KEY ({xml_schemas_pk}));")

    connection.commit()


def add_schema(schema, connection):
    """
    Extracts schema data from a file, registers the schema in the meta info table, and
    creates the tables described in the schema.

    :param schema: a dictionary containing the file pattern,
                        schema's update time, schema description, and the data schema
    :type schema: dict
    :param connection: a connection to the meta database
    :type connection: psycopg2.extension.connection

    :return:
    """
    create_schemas_meta_table(connection)

    file_pattern = schema['meta']['files']
    time = schema['meta']['version']
    description = schema['meta']['description']
    processing_schema = json.dumps(schema['processing'])

    cur = connection.cursor()
    cur.execute(
        f"INSERT INTO {xml_schemas_table} "
        f"({file_pattern_field}, {schema_time_field}, {schema_desc_field}, {proc_schema_field}) "
                
        "VALUES "
        f"('{file_pattern}', '{time}', '{description}', '{processing_schema}'::json) "
                
        f"ON CONFLICT DO NOTHING;")
    connection.commit()


def find_schema(object_key, connection):
    """
    Searches the meta info table for schemas matching the file's name.
    At most one match (with the latest timestamp) is returned.

    :param object_key: the file's name
    :type object_key: str
    :param connection: a connection to the database
    :return: a list containing the meta data about the first matching pattern,
            in the format ``(file pattern, schema version timestamp, schema description, processing schema)``
    :type: tuple
    """
    cur = connection.cursor()
    cur.execute(
        f"SELECT * FROM {xml_schemas_table} AS t "
        f"WHERE '{object_key}' LIKE t.{file_pattern_field} "
        f"ORDER BY {schema_time_field} DESC "
        f"LIMIT 1;")  # Todo: use the publication date from the xml to filter the schemas

    rows = cur.fetchall()
    return rows[0] if len(rows) > 0 else None


def expand_prefix(tag, prefixes):
    """
    Substitutes the namespace prefix, if any, with the actual namespace in an XML tag.

    :param tag: the XML tag
    :type tag: str
    :param prefixes: the prefix mapping
    :type prefixes: dict
    :return: the tag with the explicit XML namespace
    """
    # See if `name` is in the form `ns:attr`
    # where `ns` is listed as an XML prefix
    parts = tag.split(':')

    # If `ns` is listed as a prefix, substitute the prefix to get `{<ns value>}attr`
    if len(parts) > 1 and parts[0] in prefixes:
        return '{' + prefixes[parts[0]] + '}' + parts[1]

    return tag


def parse_val(raw_val, val_type):
    if val_type == 'int':
        return int(raw_val)
    elif val_type == 'timestamp':
        datetime.strptime(raw_val, '%Y-%m-%dT%H:%M:%SZ')  # Just for validating the format
        return raw_val
    elif val_type == 'float':
        return Decimal(raw_val)
    elif val_type == 'bool':
        return bool(raw_val)
    else:
        return raw_val


def extract_data(root, data_sch, pref, log):  # Todo: ideally, replace with XSLT
    """
    Parses an XML document following a schema.
    
    :param root: the root node of the XML document
    :type root: xml.etree.Element
    :param data_sch: the schema for extracting fields
    :type data_sch: dict
    :param pref: the mapping of namespace prefixes
    :type pref: dict
    :param log: a logger function that takes a string as a single argument

    :return:
    :type: dict
    """
    record = {}

    for entry in data_sch:
        # Check if the schema entry represents an array of nodes
        entry_is_array = entry.strip().endswith('[]')

        # We won't need the brackets anymore
        # Also, convert prefixes to XML namespace prefixes
        name = entry.strip().replace('.', ':').replace('[]', '')

        # There can be 4 types of entries:
        # 0. attribute entry (one that starts with an underscore)
        # 1. map entry
        # 2. list entry
        # 3. entry without children

        # 0. attribute entry (one that starts with an underscore)
        if name.startswith('_'):
            attrib = expand_prefix(name.strip('_:'),
                                   pref)

            attrib_props = data_sch[entry].split(',')

            attrib_type = attrib_props[0].strip()
            field_name = attrib_props[1].strip()

            raw_val = root.get(attrib)

            try:
                record[field_name] = parse_val(raw_val, attrib_type)
            except ValueError:
                # Todo: start using `logging` instead
                log(f"\textract_data: [error] Couldn't parse `@{attrib}` for a `{root.tag}` node\n"
                    f"\t                      (wrong attribute type)\n"
                    f"Node's attributes:\n"
                    f"{json.dumps(root.attrib, indent=2)}\n"
                    f"\t                      Writing <parsing error> for `{field_name}`\n")
                record[field_name] = '<parsing error (0)>'
            except TypeError:
                log(f"\textract_data: [error] Couldn't parse `@{attrib}` for a `{root.tag}` node\n"
                    f"\t                      (missing attribute)\n"
                    f"Node's attributes:\n"
                    f"{json.dumps(root.attrib, indent=2)}\n"
                    f"\t                      Writing <missing> (1) for `{field_name}`\n")
                record[field_name] = '<missing>'

        # Other type of nodes
        else:
            # Start by getting an iterator for all the nodes that match the entry
            pattern = expand_prefix(name, pref)
            matching_nodes = root.iter(pattern)
            field_name = name
            sub_records = []

            for node in matching_nodes:
                # 1. map entry - extract the data from the current node using the map as a schema
                if isinstance(data_sch[entry], dict):
                    sub_rec = extract_data(node, data_sch[entry], pref, log)
                    sub_records.append(sub_rec)

                # 2. list entry - use the list elements as options for the schema of the current node
                elif isinstance(data_sch[entry], list):
                    options = data_sch[entry]

                    # Go over the patterns in the list
                    for option in options:
                        pattern1 = option['_']
                        match = node.find(pattern1, pref)
                        
                        if match is not None:
                            del option['_']

                            sub_rec = extract_data(match, option, pref, log)
                            sub_records.append(sub_rec)

                            option['_'] = pattern1
                            break

                    continue

                # 3. entry without children
                else:
                    node_props = data_sch[entry].split(',')

                    # Where to get the value from (an attribute or the text)
                    getter = node_props[0].strip()  # has one of the two forms: `_.<attribute name>` or `text`
                    is_attrib = getter.startswith('_')

                    val_type = node_props[1].strip()
                    field_name = node_props[2].strip()

                    if is_attrib:
                        attrib = expand_prefix(getter.split('.')[1].strip(),
                                               pref)
                        raw_val = node.get(attrib)
                    else:
                        raw_val = node.text

                    try:
                        sub_rec = parse_val(raw_val, val_type)
                    except ValueError:
                        log(f"\textract_data: [error] Couldn't parse `{entry}` for a `{root.tag}` node\n"
                            f"\t                      (wrong value format)\n"
                            f"Node attributes:\n"
                            f"{json.dumps(root.attrib, indent=2)}\n"
                            f"\t                      Writing <parsing error> for `{field_name}`\n")
                        sub_rec = '<parsing error (2)>'
                    except TypeError:
                        log(f"\textract_data: [error] Couldn't parse `{entry}` for a `{root.tag}` node\n"
                            f"\t                      (missing value)\n"
                            f"Node attributes:\n"
                            f"{json.dumps(root.attrib, indent=2)}\n"
                            f"\t                      Writing <missing> (2) for `{field_name}`\n")
                        sub_rec = '<missing>'

                    sub_records.append(sub_rec)

                # If the entry isn't an array, we can stop after processing the first matching node
                if not entry_is_array:
                    break

            # If the entry isn't an array,
            # unwrap the record out of the list
            if not entry_is_array:
                if len(sub_records) > 0:
                    record[field_name] = sub_records[0]
                else:
                    record[field_name] = '<missing>'

                    log(f"\textract_data: [error] No value found for `{field_name}`.`\n"
                        f"\t                      Writing <missing> (3) for `{field_name}`\n")
                    sub_records.append(
                        {'<missing>': f'{entry}'}
                    )
            # Otherwise, use the list
            else:
                record[field_name] = sub_records

    return record

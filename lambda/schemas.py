import json
from psycopg2.extras import execute_batch

#
# The table for storing known schemas
#

schemas_table = 'schemas'
schema_pattern_field, schema_pattern_props = 'schema_pattern', 'text PRIMARY KEY'
schema_desc_field, schema_desc_props = 'schema_desc', 'text'
schema_tables_field, schema_tables_props = 'schema_tables', 'json NOT NULL'


def create_schemas_meta_table(connection):
    """
    Creates a meta info table for storing known schemas.

    :param connection: a connection to the database
    """
    cur = connection.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {schemas_table} ("
                f"{schema_pattern_field} {schema_pattern_props},"
                f"{schema_desc_field} {schema_desc_props},"
                f"{schema_tables_field} {schema_tables_props});")

    connection.commit()


def process_schema(schema_json, connection):
    """
    Extracts schema data from a file, registers the schema in the meta info table, and
    creates the tables described in the schema.

    :param schema_json:
    :param connection:
    :return:
    """
    create_schemas_meta_table(connection)

    schema = json.loads(schema_json)

    tables = schema["tables"]
    for tb in tables:
        create_table_from_schema(tb, connection)

    add_schema(schema, connection)


def add_schema(schema_json, connection):
    """
    Adds a schema to the meta info table.

    :param schema_json: the schema to be added
    :type schema_json: dict
    :param connection: a connection to the database
    """
    decsription = schema_json['description']
    tables = schema_json['tables']
    pattern = schema_json['pattern']

    # Converting the `tables` array to a JSON string, also escaping the apostrophes for SQL
    tables_json = "'[" + \
                  ", ".join(
                      [json.dumps(x).replace("'", "''") for x in tables]
                  ) + "]'::json"

    cur = connection.cursor()
    cur.execute(f"INSERT INTO {schemas_table} "
                f"({schema_pattern_field}, {schema_desc_field}, {schema_tables_field}) "
                "VALUES "
                f"('{pattern}', '{decsription}', {tables_json}) "
                f"ON CONFLICT DO NOTHING;")
    connection.commit()


def find_schema(object_key, connection):
    """
    Searches the meta info table for schemas matching the file's name.
    At most one match is returned.

    :param object_key: the file's name
    :type object_key: str
    :param connection: a connection to the database
    :return: a list containing the meta data about the first matching pattern,
            in the format ``[pattern, tables]``,
            where ``pattern`` and ``tables`` are as in
            :func:`add_schema <add_schema(pattern, tables)>`
    :type: list
    """
    cur = connection.cursor()
    cur.execute(f"SELECT * FROM {schemas_table} AS t "
                f"WHERE '{object_key}' LIKE t.{schema_pattern_field} "
                f"LIMIT 1;")

    rows = cur.fetchall()
    return rows[0] if len(rows) > 0 else None


def create_table_from_schema(table_json, connection):
    """
    Creates a table described by a `dict` parsed from a JSON string.

    :param table_json: the description of the table
    :param connection: a connection to the database
    """
    cur = connection.cursor()

    tb_name = table_json["table"]
    tb_fields = table_json["fields"]

    fields = {}

    for fd in tb_fields.keys():
        fd_props = tb_fields[fd]
        fd_string = ''
        fd_ext_string = ''

        fd_type = fd_props["type"]

        if fd_type == 'state2':
            fd_string += 'char(2)'
        elif fd_type == 'enum':
            fd_string += 'text'
        elif fd_type == 'zip':
            fd_string += 'integer'
            fd_ext_string += 'smallint'
        else:
            fd_string += fd_type

        fd_nullable = fd_props['nullable'] if 'nullable' in fd_props else True
        if not fd_nullable:
            fd_string += ' NOT NULL'

        if 'range' in fd_props:
            rng = fd_props['range'].split(':')
            rng_checks = []
            if rng[0] != '':
                rng_checks.append(f'{fd} >= {rng[0]}')
            if rng[1] != '':
                rng_checks.append(f'{fd} <= {rng[1]}')
            rng_string = ' AND '.join(rng_checks)

            if rng_string != '':
                fd_string += f' CHECK ({rng_string})'
        if fd_type == 'zip':
            fd_string += f' CHECK ({fd} >= 0 AND {fd} <= 99999)'
            fd_ext_string += f' CHECK ({fd}_ext >= 0 AND {fd}_ext <= 9999)'

        if 'ref' in fd_props:
            fd_string += f" REFERENCES {fd_props['ref']} ON DELETE RESTRICT"

        fields[fd] = fd_string

        if fd_type == 'zip':
            fields[fd + '_ext'] = fd_ext_string

    fields_string = ', '.join([f'{x} {fields[x]}' for x in fields])
    tb_pk = ", ".join(table_json["primary_key"])

    cur.execute(f"CREATE TABLE IF NOT EXISTS {tb_name} ("
                f"{fields_string},"
                f" PRIMARY KEY ({tb_pk}));")
    connection.commit()


def normalized_zip_code(zip_code):
    """
    Converts 5- and 9-digit zip codes into pairs of the 5-digit zip code and 4-digit extension.
    If the 4-digit extension is missing, use 'NULL'.

    :param zip_code:
    :type zip_code: str
    :return: a list consisting of 2 elements---the 5-digit zip code,
             and an optional 4-digit extension (default=None)
    """
    zip_code = zip_code.strip()
    return [int(zip_code), None] \
        if len(zip_code) < 6 \
        else [int(zip_code[:5]), int(zip_code[5:].strip('- '))]


def generate_data_processors(table_json, connection):
    """
    Generates functions for processing data coming from a file
    and to be written to a table in the database.

    :param table_json: the description of a table
    :param connection: a connection to the database
    :return: a pair of functions, ``(parse_line, write_to_db)``;

            ``parse_record`` looks up the values of the fields in a line by the field's number,
            and converts them to appropriate types according to the table description.

            ``write_to_db`` writes a batch of parsed records
            to the appropriate table in the database
    """

    def parse_record(fields):
        """
        Converts the fields specified in the table's description to the appropriate types,
        and forms a record to be sent to the database.

        :param fields: all the fields contained in a line
        :return: a dict containing the fields of the record
        :type: dict
        """
        field_decriptions = table_json['fields']
        record = {}

        for fd in field_decriptions:
            fd_props = field_decriptions[fd]
            fd_type = fd_props['type']
            fd_column = fd_props['column']
            fd_val = fields[fd_column]

            if fd_type in ('integer', 'smallint'):
                record[fd] = int(fd_val) if fd_val != 'NULL' else None

            elif fd_type in ('state2', 'text'):
                record[fd] = fd_val.upper() if fd_val != 'NULL' else None

            elif fd_type == 'zip':
                zip_code = normalized_zip_code(fd_val) if fd_val != 'NULL' else [None, None]
                record[fd] = zip_code[0]
                record[fd + '_ext'] = zip_code[1]

            elif fd_type == 'enum':
                values = fd_props['values']
                record[fd] = values[fd_val] if fd_val != 'NULL' else None

            elif fd_type == 'real':
                record[fd] = float(fd_val) if fd_val != 'NULL' else None

            else:
                record[fd] = str(fd_val) if fd_val != 'NULL' else None

        return record

    def write_to_db(records_batch):
        """
        Sends buffered records to the DB. The buffer is expected in
        the form of a list of dictionaries, each dictionary representing
        a single record.

        :param records_batch:
        :type records_batch: list(dict)
        """
        cur = connection.cursor()

        table = table_json['table']
        fields = table_json['fields']
        fields_list = ', '.join(fields.keys())
        values_list = ')s, %('.join(fields.keys())
        for fd in fields:
            if fields[fd]['type'] == 'zip':
                fields_list += f', {fd}_ext'
                values_list += f')s, %({fd}_ext'

        execute_batch(cur,
                      f"INSERT INTO {table} "
                      f"({fields_list}) "
                      "VALUES "
                      f"(%({values_list})s)"
                      " ON CONFLICT DO NOTHING;",
                      records_batch)

        connection.commit()

    return parse_record, write_to_db

import os, json
import pandas as pd
from  dotenv import load_dotenv
from sqlalchemy import create_engine, text

# initializing environment variables
load_dotenv()
db_url = os.getenv("DB_URL")

# initializing variables
risk_consulting_momentum_index_df = pd.DataFrame()

# parse dataframe-style json into normal records
def json_parser(raw_output):
    parsed_output = raw_output
    while isinstance(parsed_output, str):
        parsed_output = json.loads(parsed_output)

    if isinstance(parsed_output, list):
        return [_parse_nested_json_values(record) for record in parsed_output]

    if isinstance(parsed_output, dict) and _is_pandas_column_oriented_json(parsed_output):
        row_keys = sorted(
            {row_key for column_values in parsed_output.values() for row_key in column_values.keys()},
            key=lambda row_key: int(row_key) if str(row_key).isdigit() else str(row_key)
        )
        records = []
        for row_key in row_keys:
            record = {}
            for column_name, column_values in parsed_output.items():
                record[column_name] = _parse_nested_json_values(column_values.get(row_key))
            records.append(record)
        return records

    return _parse_nested_json_values(parsed_output)

def _is_pandas_column_oriented_json(parsed_output):
    if not parsed_output:
        return False
    return all(isinstance(column_values, dict) for column_values in parsed_output.values())

def _parse_nested_json_values(value):
    if isinstance(value, dict):
        return {key: _parse_nested_json_values(inner_value) for key, inner_value in value.items()}
    if isinstance(value, list):
        return [_parse_nested_json_values(inner_value) for inner_value in value]
    if isinstance(value, str):
        stripped_value = value.strip()
        if stripped_value.startswith("{") or stripped_value.startswith("["):
            try:
                return _parse_nested_json_values(json.loads(stripped_value))
            except json.JSONDecodeError:
                return value
    return value

# reading data from table
def risk_practice_momentum_data_call():
    engine = create_engine(
        url=db_url,
        pool_pre_ping=True
    )
    query = text("select * from risk_practice_momentum_index;")
    with engine.begin() as conn:
        risk_consulting_momentum_index_df = pd.read_sql(con=conn, sql=query)

    risk_consulting_momentum_index_json = risk_consulting_momentum_index_df.to_json(
        orient="records",
        date_format="iso"
    )
    output = json.dumps(json_parser(risk_consulting_momentum_index_json), indent=4)
    return output

if __name__ == "__main__":
    print(risk_practice_momentum_data_call())
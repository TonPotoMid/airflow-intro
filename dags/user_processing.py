from datetime import datetime

import requests
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.sdk import dag, task
from airflow.sdk.bases.sensor import PokeReturnValue

API_URL = "https://randomuser.me/api/"


@dag(
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["tp"],
)
def user_processing():

    create_table = SQLExecuteQueryOperator(
        task_id="create_table",
        conn_id="postgres",
        sql="""
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(64) PRIMARY KEY,
            firstname VARCHAR(255),
            lastname VARCHAR(255),
            email VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    )

    @task.sensor(poke_interval=30, timeout=300)
    def is_api_available() -> PokeReturnValue:
        response = requests.get(API_URL, timeout=10)
        if response.status_code == 200:
            return PokeReturnValue(is_done=True, xcom_value=response.json())
        return PokeReturnValue(is_done=False, xcom_value=None)

    @task
    def extract_user(payload):
        return payload["results"][0]

    @task
    def process_user(user_info):
        return {
            "id": user_info["login"]["uuid"],
            "firstname": user_info["name"]["first"],
            "lastname": user_info["name"]["last"],
            "email": user_info["email"],
        }

    @task
    def save_user(user):
        hook = PostgresHook(postgres_conn_id="postgres")
        hook.insert_rows(
            table="users",
            rows=[(user["id"], user["firstname"], user["lastname"], user["email"])],
            target_fields=["id", "firstname", "lastname", "email"],
        )

    user = process_user(extract_user(is_api_available()))
    create_table >> user
    save_user(user)



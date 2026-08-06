import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def main() -> None:
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from .env")

    engine = create_engine(database_url)

    with engine.connect() as connection:
        postgres_version = connection.execute(
            text("SELECT version();")
        ).scalar_one()

        postgis_version = connection.execute(
            text("SELECT PostGIS_Version();")
        ).scalar_one()

    print("Database connection successful")
    print(f"PostgreSQL: {postgres_version}")
    print(f"PostGIS: {postgis_version}")


if __name__ == "__main__":
    main()

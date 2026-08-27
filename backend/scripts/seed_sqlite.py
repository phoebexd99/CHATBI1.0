from backend.app.config import settings
from backend.app.db import Database, seed_sqlite


if __name__ == "__main__":
    database = Database(settings.database_url)
    seed_sqlite(database)
    print(f"Seeded synthetic commerce data at {settings.database_url}")


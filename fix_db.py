from app import app, db
from sqlalchemy import inspect
from sqlalchemy import text

def fix_database():
    with app.app_context():
        inspector = inspect(db.engine)
        for table_name in db.metadata.tables:
            if not inspector.has_table(table_name):
                print(f"Table {table_name} missing. Creating...")
                db.metadata.tables[table_name].create(db.engine)
                continue
            
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            table = db.metadata.tables[table_name]
            
            for column in table.columns:
                if column.name not in existing_columns:
                    print(f"Adding missing column {column.name} to {table_name}")
                    # Construct alter table statement manually for sqlite
                    col_type = column.type.compile(db.engine.dialect)
                    try:
                        db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}"))
                        db.session.commit()
                    except Exception as e:
                        print(f"Failed to add column {column.name}: {e}")
                        db.session.rollback()

if __name__ == "__main__":
    fix_database()
    print("Database sync complete.")

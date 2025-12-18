#!/usr/bin/env python3
"""Run database migrations using asyncpg."""
import asyncio
import asyncpg
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


async def run_migration():
    """Run the init_db.sql migration."""
    # Get database connection details
    db_url = settings.get_database_url()
    
    # Parse connection string for asyncpg
    # Format: postgresql+asyncpg://user:pass@host:port/dbname
    # asyncpg expects: postgresql://user:pass@host:port/dbname
    if db_url.startswith("postgresql+asyncpg://"):
        db_url_asyncpg = db_url.replace("postgresql+asyncpg://", "postgresql://")
    else:
        db_url_asyncpg = db_url
    
    print(f"Connecting to database...")
    print(f"URL: {db_url_asyncpg.replace(settings.POSTGRES_PASSWORD, '***') if settings.POSTGRES_PASSWORD else db_url_asyncpg}")
    
    try:
        # Use DATABASE_URL if set, otherwise construct from components
        db_url = settings.get_database_url()
        
        # Extract connection details from URL
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Parse URL to get individual components for asyncpg.connect
        # Format: postgresql://user:pass@host:port/dbname
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url)
        
        user = parsed.username or settings.POSTGRES_USER
        password = parsed.password or settings.POSTGRES_PASSWORD
        host = parsed.hostname or settings.POSTGRES_HOST
        port = parsed.port or settings.POSTGRES_PORT
        database = parsed.path.lstrip('/') or settings.POSTGRES_DB
        
        print(f"Connecting as user: {user} to {host}:{port}/{database}")
        
        # Connect to database using connection parameters
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        print("✅ Connected to database")
        
        # Read SQL file
        sql_file = Path(__file__).parent / "init_db.sql"
        if not sql_file.exists():
            print(f"❌ SQL file not found: {sql_file}")
            return
        
        print(f"Reading SQL file: {sql_file}")
        sql_content = sql_file.read_text()
        
        # Split by semicolons and execute each statement
        statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]
        
        print(f"Executing {len(statements)} SQL statements...")
        
        for i, statement in enumerate(statements, 1):
            if statement:
                try:
                    await conn.execute(statement)
                    print(f"  ✅ Statement {i}/{len(statements)} executed")
                except Exception as e:
                    # Some statements might fail if they already exist (IF NOT EXISTS)
                    if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                        print(f"  ⚠️  Statement {i}/{len(statements)}: {str(e)[:80]}... (may already exist)")
                    else:
                        print(f"  ❌ Error in statement {i}/{len(statements)}: {e}")
                        print(f"     Statement: {statement[:100]}...")
        
        await conn.close()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_migration())


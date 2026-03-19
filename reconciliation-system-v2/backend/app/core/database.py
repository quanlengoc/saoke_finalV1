"""
Database Manager
Supports SQLite (dev) and Oracle (prod) with dynamic switching
"""

import os
from typing import Optional, Dict, Any, Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool

from app.core.config import get_settings, get_config_reader, get_storage_path


# Base class for all models
Base = declarative_base()


class DatabaseManager:
    """
    Manages database connections for both app database and external databases
    Supports SQLite (development) and Oracle (production)
    """
    
    _engines: Dict[str, Any] = {}
    _session_factories: Dict[str, sessionmaker] = {}
    
    @classmethod
    def get_app_engine(cls):
        """Get the application database engine (SQLite or Oracle based on config)"""
        if 'app' not in cls._engines:
            settings = get_settings()
            config = get_config_reader()
            
            if settings.DB_TYPE.lower() == 'sqlite':
                # SQLite configuration
                db_config = config.get_database_config('app')
                db_path = db_config.get('path', './data/app.db')
                
                # Convert to absolute path - use BACKEND_DIR for database location
                if not Path(db_path).is_absolute():
                    db_path = settings.BACKEND_DIR / db_path
                
                # Ensure directory exists
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                
                engine = create_engine(
                    f"sqlite:///{db_path}",
                    connect_args={"check_same_thread": False, "timeout": 60},
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    echo=False  # Tắt SQL logging để khởi động nhanh (bật khi cần debug)
                )
                
                # Enable WAL mode + foreign keys for SQLite
                # WAL allows concurrent reads & writes, preventing 'database is locked'
                @event.listens_for(engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    try:
                        cursor.execute("PRAGMA journal_mode=WAL")
                    except Exception:
                        pass  # WAL may fail if DB is locked by another process; non-fatal
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.execute("PRAGMA busy_timeout=60000")
                    cursor.close()
                
            elif settings.DB_TYPE.lower() == 'oracle':
                # Oracle configuration
                db_config = config.get_database_config('app')
                dsn = db_config.get('dsn')
                user = db_config.get('user')
                password = db_config.get('password')
                
                engine = create_engine(
                    f"oracle+oracledb://{user}:{password}@{dsn}",
                    echo=settings.DEBUG
                )
            else:
                raise ValueError(f"Unsupported database type: {settings.DB_TYPE}")
            
            cls._engines['app'] = engine
        
        return cls._engines['app']
    
    @classmethod
    def get_session_factory(cls, name: str = 'app') -> sessionmaker:
        """Get session factory for a database"""
        if name not in cls._session_factories:
            if name == 'app':
                engine = cls.get_app_engine()
            else:
                engine = cls.get_external_engine(name)
            
            cls._session_factories[name] = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine
            )
        
        return cls._session_factories[name]
    
    @classmethod
    def get_external_engine(cls, connection_name: str):
        """
        Get engine for external database (VNPT Money, etc.)
        
        Args:
            connection_name: Name of connection defined in config.ini
        
        Returns:
            SQLAlchemy Engine
        """
        if connection_name not in cls._engines:
            settings = get_settings()
            config = get_config_reader()
            
            # Check mock mode
            if settings.MOCK_MODE or config.is_mock_mode():
                # In mock mode, return None - data will be loaded from CSV
                return None
            
            db_config = config.get_database_config(connection_name)
            db_type = db_config.get('type', 'oracle').lower()
            
            if db_type == 'oracle':
                dsn = db_config.get('dsn')
                user = db_config.get('user')
                password = db_config.get('password')
                
                engine = create_engine(
                    f"oracle+oracledb://{user}:{password}@{dsn}",
                    echo=settings.DEBUG
                )
            elif db_type == 'sqlite':
                db_path = db_config.get('path')
                engine = create_engine(
                    f"sqlite:///{db_path}",
                    connect_args={"check_same_thread": False}
                )
            else:
                raise ValueError(f"Unsupported database type: {db_type}")
            
            cls._engines[connection_name] = engine
        
        return cls._engines[connection_name]
    
    @classmethod
    def init_app_db(cls):
        """Initialize application database - create all tables"""
        engine = cls.get_app_engine()
        Base.metadata.create_all(bind=engine)
    
    @classmethod
    def get_app_session(cls) -> Generator[Session, None, None]:
        """Get a database session for the app database"""
        SessionLocal = cls.get_session_factory('app')
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    @classmethod
    @contextmanager
    def session_scope(cls, name: str = 'app'):
        """Provide a transactional scope around a series of operations"""
        SessionLocal = cls.get_session_factory(name)
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    @classmethod
    def execute_query(cls, connection_name: str, sql: str, params: Dict = None) -> list:
        """
        Execute a SQL query on an external database
        
        Args:
            connection_name: Database connection name
            sql: SQL query string
            params: Query parameters
        
        Returns:
            List of result rows as dictionaries
        """
        engine = cls.get_external_engine(connection_name)
        
        if engine is None:
            # Mock mode - return empty list (data should be loaded from CSV)
            return []
        
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    
    @classmethod
    def create_temp_table(cls, table_name: str, df, connection_name: str = 'app'):
        """
        Create a temporary table from a pandas DataFrame

        Args:
            table_name: Name for the temp table
            df: Pandas DataFrame
            connection_name: Database connection name
        """
        from app.core.sql_security import SqlGuard
        SqlGuard.validate_table_name(table_name, context="create_temp_table")

        engine = cls.get_app_engine() if connection_name == 'app' else cls.get_external_engine(connection_name)

        # Use pandas to_sql for simplicity
        df.to_sql(table_name, engine, if_exists='replace', index=False)
    
    @classmethod
    def drop_temp_table(cls, table_name: str, connection_name: str = 'app'):
        """
        Drop a temporary table

        Args:
            table_name: Name of the table to drop
            connection_name: Database connection name
        """
        from app.core.sql_security import SqlGuard
        SqlGuard.validate_table_name(table_name, context="drop_temp_table")

        engine = cls.get_app_engine() if connection_name == 'app' else cls.get_external_engine(connection_name)

        with engine.connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
            conn.commit()
    
    @classmethod
    def execute_sql_on_temp(cls, sql: str, params: Dict = None) -> list:
        """
        Execute SQL on app database (for temp table queries)

        Args:
            sql: SQL query (must be SELECT — validated by SqlGuard)
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        from app.core.sql_security import SqlGuard
        SqlGuard.validate_query(sql, context="execute_sql_on_temp")

        engine = cls.get_app_engine()

        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]


# Dependency for FastAPI
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to get database session"""
    yield from DatabaseManager.get_app_session()

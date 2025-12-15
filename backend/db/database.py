import aiosqlite
import uuid
import time
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from config import settings
from models import Spool, SpoolCreate, SpoolUpdate, Printer, PrinterCreate, PrinterUpdate


SCHEMA = """
-- Spools table
CREATE TABLE IF NOT EXISTS spools (
    id TEXT PRIMARY KEY,
    tag_id TEXT UNIQUE,
    material TEXT NOT NULL,
    subtype TEXT,
    color_name TEXT,
    rgba TEXT,
    brand TEXT,
    label_weight INTEGER DEFAULT 1000,
    core_weight INTEGER DEFAULT 250,
    weight_new INTEGER,
    weight_current INTEGER,
    slicer_filament TEXT,
    note TEXT,
    added_time INTEGER,
    encode_time INTEGER,
    added_full INTEGER DEFAULT 0,
    consumed_since_add REAL DEFAULT 0,
    consumed_since_weight REAL DEFAULT 0,
    data_origin TEXT,
    tag_type TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Printers table
CREATE TABLE IF NOT EXISTS printers (
    serial TEXT PRIMARY KEY,
    name TEXT,
    model TEXT,
    ip_address TEXT,
    access_code TEXT,
    last_seen INTEGER,
    config TEXT,
    auto_connect INTEGER DEFAULT 0
);

-- K-Profiles table
CREATE TABLE IF NOT EXISTS k_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spool_id TEXT REFERENCES spools(id) ON DELETE CASCADE,
    printer_serial TEXT REFERENCES printers(serial) ON DELETE CASCADE,
    extruder INTEGER,
    nozzle_diameter TEXT,
    nozzle_type TEXT,
    k_value TEXT,
    name TEXT,
    cali_idx INTEGER,
    setting_id TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Usage history table
CREATE TABLE IF NOT EXISTS usage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spool_id TEXT REFERENCES spools(id) ON DELETE CASCADE,
    printer_serial TEXT,
    print_name TEXT,
    weight_used REAL,
    timestamp INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_spools_tag_id ON spools(tag_id);
CREATE INDEX IF NOT EXISTS idx_spools_material ON spools(material);
CREATE INDEX IF NOT EXISTS idx_k_profiles_spool ON k_profiles(spool_id);
CREATE INDEX IF NOT EXISTS idx_usage_history_spool ON usage_history(spool_id);
"""


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Connect to database and run migrations."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(SCHEMA)
        await self._connection.commit()

    async def disconnect(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    # ============ Spool Operations ============

    async def get_spools(self) -> list[Spool]:
        """Get all spools."""
        async with self.conn.execute("SELECT * FROM spools ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [Spool(**dict(row)) for row in rows]

    async def get_spool(self, spool_id: str) -> Optional[Spool]:
        """Get a single spool by ID."""
        async with self.conn.execute("SELECT * FROM spools WHERE id = ?", (spool_id,)) as cursor:
            row = await cursor.fetchone()
            return Spool(**dict(row)) if row else None

    async def create_spool(self, spool: SpoolCreate) -> Spool:
        """Create a new spool."""
        spool_id = str(uuid.uuid4())
        now = int(time.time())

        await self.conn.execute(
            """INSERT INTO spools (id, tag_id, material, subtype, color_name, rgba, brand,
               label_weight, core_weight, weight_new, weight_current, slicer_filament,
               note, data_origin, tag_type, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (spool_id, spool.tag_id, spool.material, spool.subtype, spool.color_name,
             spool.rgba, spool.brand, spool.label_weight, spool.core_weight,
             spool.weight_new, spool.weight_current, spool.slicer_filament,
             spool.note, spool.data_origin, spool.tag_type, now, now)
        )
        await self.conn.commit()
        return await self.get_spool(spool_id)

    async def update_spool(self, spool_id: str, spool: SpoolUpdate) -> Optional[Spool]:
        """Update an existing spool."""
        existing = await self.get_spool(spool_id)
        if not existing:
            return None

        # Build update query dynamically for non-None fields
        updates = []
        values = []
        for field, value in spool.model_dump(exclude_unset=True).items():
            updates.append(f"{field} = ?")
            values.append(value)

        if updates:
            updates.append("updated_at = ?")
            values.append(int(time.time()))
            values.append(spool_id)

            query = f"UPDATE spools SET {', '.join(updates)} WHERE id = ?"
            await self.conn.execute(query, values)
            await self.conn.commit()

        return await self.get_spool(spool_id)

    async def delete_spool(self, spool_id: str) -> bool:
        """Delete a spool."""
        cursor = await self.conn.execute("DELETE FROM spools WHERE id = ?", (spool_id,))
        await self.conn.commit()
        return cursor.rowcount > 0

    # ============ Printer Operations ============

    async def get_printers(self) -> list[Printer]:
        """Get all printers."""
        async with self.conn.execute("SELECT * FROM printers ORDER BY name") as cursor:
            rows = await cursor.fetchall()
            return [Printer(**{**dict(row), 'auto_connect': bool(row['auto_connect'])}) for row in rows]

    async def get_printer(self, serial: str) -> Optional[Printer]:
        """Get a single printer by serial."""
        async with self.conn.execute("SELECT * FROM printers WHERE serial = ?", (serial,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return Printer(**{**dict(row), 'auto_connect': bool(row['auto_connect'])})
            return None

    async def create_printer(self, printer: PrinterCreate) -> Printer:
        """Create or update a printer."""
        now = int(time.time())

        await self.conn.execute(
            """INSERT INTO printers (serial, name, model, ip_address, access_code, last_seen, auto_connect)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(serial) DO UPDATE SET
               name = excluded.name,
               model = excluded.model,
               ip_address = excluded.ip_address,
               access_code = excluded.access_code,
               last_seen = excluded.last_seen,
               auto_connect = excluded.auto_connect""",
            (printer.serial, printer.name, printer.model, printer.ip_address,
             printer.access_code, now, int(printer.auto_connect))
        )
        await self.conn.commit()
        return await self.get_printer(printer.serial)

    async def update_printer(self, serial: str, printer: PrinterUpdate) -> Optional[Printer]:
        """Update an existing printer."""
        existing = await self.get_printer(serial)
        if not existing:
            return None

        updates = []
        values = []
        for field, value in printer.model_dump(exclude_unset=True).items():
            if field == 'auto_connect':
                value = int(value) if value is not None else None
            updates.append(f"{field} = ?")
            values.append(value)

        if updates:
            values.append(serial)
            query = f"UPDATE printers SET {', '.join(updates)} WHERE serial = ?"
            await self.conn.execute(query, values)
            await self.conn.commit()

        return await self.get_printer(serial)

    async def delete_printer(self, serial: str) -> bool:
        """Delete a printer."""
        cursor = await self.conn.execute("DELETE FROM printers WHERE serial = ?", (serial,))
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_auto_connect_printers(self) -> list[Printer]:
        """Get printers with auto_connect enabled."""
        async with self.conn.execute("SELECT * FROM printers WHERE auto_connect = 1") as cursor:
            rows = await cursor.fetchall()
            return [Printer(**{**dict(row), 'auto_connect': True}) for row in rows]


# Global database instance
_db: Optional[Database] = None


async def get_db() -> Database:
    """Get database instance."""
    global _db
    if _db is None:
        _db = Database(settings.database_path)
        await _db.connect()
    return _db

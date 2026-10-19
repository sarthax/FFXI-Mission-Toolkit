# Persistence / DB Gap Report (proposal only; NOTHING executed)

The live DB is MyISAM and may differ from repo SQL: dry-check first and back up before any import.

## Proposed additive migration
Derive exact columns from LSB `sql/char_chocobos.sql`; do not invent any.

```sql
-- up
CREATE TABLE IF NOT EXISTS char_chocobos ( /* 29 columns copied from LSB, charid PK */ ) ENGINE=MyISAM;
ALTER TABLE char_pet ADD COLUMN chocobo_user_data BLOB NULL;
-- down
ALTER TABLE char_pet DROP COLUMN chocobo_user_data;
DROP TABLE IF EXISTS char_chocobos;
```

Existing `char_pet.chocoboid` (packed name pair) stays untouched. MyISAM has no FK cascade, so the delete-char path must delete `char_chocobos` rows explicitly.

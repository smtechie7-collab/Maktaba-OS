-- Migration: 004_add_block_versioning
-- Description: Adds strict version tracking and an audit history table for Content Blocks to prevent data loss.

ALTER TABLE Content_Blocks ADD COLUMN version_id INTEGER DEFAULT 1;

CREATE TABLE IF NOT EXISTS Content_Blocks_History (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    block_id INTEGER NOT NULL,
    version_id INTEGER NOT NULL,
    chapter_id INTEGER NOT NULL,
    content_data TEXT,
    sequence_number INTEGER,
    is_active INTEGER,
    archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (block_id) REFERENCES Content_Blocks(id)
);

CREATE TRIGGER IF NOT EXISTS trg_content_blocks_audit
AFTER UPDATE ON Content_Blocks
FOR EACH ROW
WHEN (NEW.content_data != OLD.content_data OR NEW.is_active != OLD.is_active)
BEGIN
    INSERT INTO Content_Blocks_History (
        block_id, version_id, chapter_id, content_data, sequence_number, is_active
    ) VALUES (
        OLD.id, OLD.version_id, OLD.chapter_id, OLD.content_data, OLD.sequence_number, OLD.is_active
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_content_blocks_increment_version
AFTER UPDATE ON Content_Blocks
FOR EACH ROW
WHEN (NEW.content_data != OLD.content_data OR NEW.is_active != OLD.is_active) AND (NEW.version_id = OLD.version_id)
BEGIN
    UPDATE Content_Blocks 
    SET version_id = OLD.version_id + 1 
    WHERE id = OLD.id;
END;
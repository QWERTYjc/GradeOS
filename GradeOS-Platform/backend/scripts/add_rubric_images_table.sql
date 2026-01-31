-- Add rubric images table
-- Store rubric images associated with grading history

CREATE TABLE IF NOT EXISTS rubric_images (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    grading_history_id TEXT NOT NULL REFERENCES grading_history(id) ON DELETE CASCADE,
    page_index INTEGER NOT NULL,
    image_data BYTEA NOT NULL,
    image_format VARCHAR(10) DEFAULT 'png',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure only one image per page per grading history
    UNIQUE(grading_history_id, page_index)
);

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_rubric_images_history_id 
ON rubric_images(grading_history_id);

-- Add comments
COMMENT ON TABLE rubric_images IS 'Rubric images table';
COMMENT ON COLUMN rubric_images.id IS 'Image unique identifier';
COMMENT ON COLUMN rubric_images.grading_history_id IS 'Associated grading history ID';
COMMENT ON COLUMN rubric_images.page_index IS 'Rubric page index (0-based)';
COMMENT ON COLUMN rubric_images.image_data IS 'Image binary data';
COMMENT ON COLUMN rubric_images.image_format IS 'Image format (png/jpg/webp)';
COMMENT ON COLUMN rubric_images.created_at IS 'Creation timestamp';

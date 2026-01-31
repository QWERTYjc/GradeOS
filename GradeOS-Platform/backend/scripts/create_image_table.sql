-- Create grading page images table (store file references, not raw bytes)
CREATE TABLE IF NOT EXISTS grading_page_images (
    id VARCHAR(100) PRIMARY KEY,
    grading_history_id VARCHAR(100) NOT NULL,
    student_key VARCHAR(200) NOT NULL,
    page_index INTEGER NOT NULL,
    file_id VARCHAR(200),
    file_url TEXT,
    content_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (grading_history_id) REFERENCES grading_history(id) ON DELETE CASCADE,

    CONSTRAINT unique_page_image UNIQUE (grading_history_id, student_key, page_index)
);

-- Ensure legacy columns are upgraded safely
ALTER TABLE grading_page_images ADD COLUMN IF NOT EXISTS file_id VARCHAR(200);
ALTER TABLE grading_page_images ADD COLUMN IF NOT EXISTS file_url TEXT;
ALTER TABLE grading_page_images ADD COLUMN IF NOT EXISTS content_type VARCHAR(100);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_page_images_history
    ON grading_page_images(grading_history_id);

CREATE INDEX IF NOT EXISTS idx_page_images_student
    ON grading_page_images(grading_history_id, student_key);

CREATE INDEX IF NOT EXISTS idx_page_images_file_id
    ON grading_page_images(file_id);

-- Add table comments
COMMENT ON TABLE grading_page_images IS 'Grading page images file references';
COMMENT ON COLUMN grading_page_images.file_id IS 'File storage ID for the page image';
COMMENT ON COLUMN grading_page_images.page_index IS 'Page index (starting from 0)';

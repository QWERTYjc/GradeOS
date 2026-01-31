-- Create grading page images table
CREATE TABLE IF NOT EXISTS grading_page_images (
    id VARCHAR(100) PRIMARY KEY,
    grading_history_id VARCHAR(100) NOT NULL,
    student_key VARCHAR(200) NOT NULL,
    page_index INTEGER NOT NULL,
    image_data BYTEA NOT NULL,
    image_format VARCHAR(10) DEFAULT 'png',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (grading_history_id) REFERENCES grading_history(id) ON DELETE CASCADE,
    
    CONSTRAINT unique_page_image UNIQUE (grading_history_id, student_key, page_index)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_page_images_history 
    ON grading_page_images(grading_history_id);

CREATE INDEX IF NOT EXISTS idx_page_images_student 
    ON grading_page_images(grading_history_id, student_key);

-- Add table comments
COMMENT ON TABLE grading_page_images IS 'Grading page images storage';
COMMENT ON COLUMN grading_page_images.image_data IS 'Image binary data (PNG/JPG format)';
COMMENT ON COLUMN grading_page_images.page_index IS 'Page index (starting from 0)';

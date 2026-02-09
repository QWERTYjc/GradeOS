import io
import asyncio
import importlib.util
import uuid
from datetime import datetime

import pytest
from PIL import Image

from src.db.postgres_grading import (
    GradingAnnotation,
    GradingPageImage,
    StudentGradingResult,
)
from src.services.pdf_exporter import export_annotated_pdf


def test_export_annotated_pdf_uses_fallback_images():
    """Ensure we can export a PDF even when page_images have no file_url."""

    if importlib.util.find_spec("reportlab") is None:
        pytest.skip("reportlab not installed in this environment")

    # Build a minimal JPEG in-memory.
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    history_id = str(uuid.uuid4())
    student_key = "student-1"
    now = datetime.now().isoformat()

    student_result = StudentGradingResult(
        id=str(uuid.uuid4()),
        grading_history_id=history_id,
        student_key=student_key,
        score=3,
        max_score=5,
        result_data={
            "question_results": [
                {
                    "question_id": "1",
                    "score": 3,
                    "max_score": 5,
                    "feedback": "ok",
                }
            ]
        },
    )

    page_images = [
        GradingPageImage(
            id=str(uuid.uuid4()),
            grading_history_id=history_id,
            student_key=student_key,
            page_index=0,
            file_id="",
            file_url=None,
            content_type="image/jpeg",
            created_at=now,
        )
    ]

    annotations = [
        GradingAnnotation(
            id=str(uuid.uuid4()),
            grading_history_id=history_id,
            student_key=student_key,
            page_index=0,
            annotation_type="score",
            bounding_box={"x_min": 0.8, "y_min": 0.1, "x_max": 0.95, "y_max": 0.16},
            text="3/5",
            color="#FF8800",
            created_by="ai",
            created_at=now,
            updated_at=now,
        )
    ]

    pdf_bytes = asyncio.run(export_annotated_pdf(
        student_result=student_result,
        page_images=page_images,
        annotations=annotations,
        include_summary=True,
        fallback_images={0: jpeg_bytes},
    ))

    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000

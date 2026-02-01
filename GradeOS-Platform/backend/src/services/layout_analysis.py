"""Layout analysis service."""

import base64
import json
from typing import List, Optional
from langchain_core.messages import HumanMessage

from src.services.chat_model_factory import get_chat_model
from ..models.region import BoundingBox, QuestionRegion, SegmentationResult
from ..utils.coordinates import normalize_coordinates
from ..config.models import get_lite_model


class LayoutAnalysisService:
    """Use an LLM to detect question regions in an exam page."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """Initialize the layout analysis service."""
        if model_name is None:
            model_name = get_lite_model()
        self.llm = get_chat_model(
            api_key=api_key,
            model_name=model_name,
            temperature=0.1,
            purpose="vision",
            enable_thinking=False,
        )
        self.model_name = model_name

    async def segment_document(
        self,
        image_data: bytes,
        submission_id: str,
        page_index: int = 0,
    ) -> SegmentationResult:
        """Detect question regions in an exam page image."""
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        prompt = (
            "Analyze this exam page image and identify all question bounding boxes.\n\n"
            "For each question, return:\n"
            "- question_id: label like 'q1', 'q2', etc.\n"
            "- bounding_box: [ymin, xmin, ymax, xmax] in normalized 0-1000 coordinates.\n\n"
            "Return JSON in this format:\n"
            "{\n"
            '  "regions": [\n'
            "    {\n"
            '      "question_id": "q1",\n'
            '      "bounding_box": [ymin, xmin, ymax, xmax]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "If no regions are found, return an empty regions list.\n"
            "Return regions in top-to-bottom order."
        )

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{image_b64}",
                },
            ]
        )

        response = await self.llm.ainvoke([message])

        result_text = response.content
        if isinstance(result_text, list):
            text_parts = []
            for item in result_text:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
            result_text = "".join(text_parts)
        elif not isinstance(result_text, str):
            result_text = str(result_text) if result_text else ""

        if "```json" in result_text:
            json_start = result_text.find("```json") + 7
            json_end = result_text.find("```", json_start)
            result_text = result_text[json_start:json_end].strip()

        result_data = json.loads(result_text)
        regions_data = result_data.get("regions", [])

        if not regions_data:
            raise ValueError(f"No regions detected for page {page_index}; manual review required.")

        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_data))
        img_width, img_height = img.size

        regions: List[QuestionRegion] = []
        for region_data in regions_data:
            question_id = region_data["question_id"]
            box_1000 = region_data["bounding_box"]

            bounding_box = normalize_coordinates(
                box_1000=box_1000,
                img_width=img_width,
                img_height=img_height,
            )

            regions.append(
                QuestionRegion(
                    question_id=question_id,
                    page_index=page_index,
                    bounding_box=bounding_box,
                    image_data=None,
                )
            )

        return SegmentationResult(
            submission_id=submission_id,
            total_pages=1,
            regions=regions,
        )

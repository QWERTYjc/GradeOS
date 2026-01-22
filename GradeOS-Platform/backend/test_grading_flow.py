import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Mock environment
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["langchain_core.language_models"] = MagicMock()
sys.modules["src.utils.error_handling"] = MagicMock()

# Import target class
# We need to mock imports that might fail
sys.path.append(os.getcwd())
from src.services.llm_reasoning import LLMReasoningClient

async def test_grade_student_flow():
    # Setup
    client = LLMReasoningClient(api_key="test")
    client.llm = AsyncMock()
    
    # Mock helper methods to avoid actual LLM calls
    client.extract_student_answers = AsyncMock(return_value={"answers": []})
    client.score_from_evidence = AsyncMock(return_value={"total_score": 10})
    client.generate_llm_self_report = AsyncMock(return_value={"overall_status": "ok"})
    client._ensure_student_result_complete = AsyncMock(side_effect=lambda result, **kwargs: result)
    client._build_student_grading_rubric_info = MagicMock(return_value="rubric_info")
    
    # Test Data
    images = [b"fake_image_data"]
    student_key = "student_1"
    parsed_rubric = {"questions": []}
    
    print("Starting test_grade_student_flow...")
    
    # Execute
    result = await client.grade_student(
        images=images,
        student_key=student_key,
        parsed_rubric=parsed_rubric
    )
    
    # Verify Phase 1: Extract
    if client.extract_student_answers.called:
        print("✅ Phase 1 (Extract) called")
    else:
        print("❌ Phase 1 (Extract) NOT called")
        
    # Verify Phase 2: Score
    if client.score_from_evidence.called:
        print("✅ Phase 2 (Score) called")
    else:
        print("❌ Phase 2 (Score) NOT called")

    # Verify Phase 3: Self Report
    if client.generate_llm_self_report.called:
        print("✅ Phase 3 (Self Report) called")
    else:
        print("❌ Phase 3 (Self Report) NOT called")
        
    # Verify Result Merging
    if result.get("self_report") == {"overall_status": "ok"}:
        print("✅ Result merged correctly")
    else:
        print(f"❌ Result merge failed: {result.get('self_report')}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_grade_student_flow())

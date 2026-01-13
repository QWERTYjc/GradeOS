
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

try:
    from src.api.routes.batch_langgraph import BatchStatusResponse
    print("Import successful")
    
    # Mock data that might be coming from the orchestrator
    state = {
        "exam_id": "test_exam",
        "student_boundaries": ["b1", "b2"],
        "student_results": [
            {"student_key": "student_1", "total_score": 10},
            {"student_key": "student_2", "total_score": 8}
        ]
    }
    
    response_data = {
        "batch_id": "test_batch",
        "exam_id": state.get("exam_id", ""),
        "status": "completed",
        "total_students": len(state.get("student_boundaries", [])),
        "completed_students": len(state.get("student_results", [])),
        "unidentified_pages": 0,
        "results": state.get("student_results")
    }
    
    print("Attempting to validate response data...")
    try:
        r = BatchStatusResponse(**response_data)
        print("Model instantiation SUCCESSFUL")
        
        # Simulate FastAPI's response_model logic
        encoded = jsonable_encoder(r)
        print("JSON encoding SUCCESSFUL")
        
    except ValidationError as e:
        print("Validation Error caught:")
        print(e.json(indent=2))
    except Exception as e:
        print(f"Other Error: {e}")

except Exception as e:
    print(f"Global Error: {e}")

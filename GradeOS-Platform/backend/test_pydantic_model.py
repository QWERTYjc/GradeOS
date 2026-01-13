
from pydantic import ValidationError
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

try:
    from src.api.routes.batch_langgraph import BatchStatusResponse
    print("Import successful")
    
    try:
        r = BatchStatusResponse(
            batch_id="test_batch",
            exam_id="test_exam",
            status="completed",
            results=[]
        )
        print("Instantiation successful")
        print(r.model_dump())
    except ValidationError as e:
        print("Validation Error:")
        print(e.json(indent=2))
    except Exception as e:
        print("Other Error during instantiation:", e)
        import traceback
        traceback.print_exc()

except ImportError as e:
    print("Import Error:", e)
except Exception as e:
    print("Global Error:", e)
    import traceback
    traceback.print_exc()

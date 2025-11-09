================================================================================
🚀 AI 批改系统 - Agent 输出汇总
================================================================================
⏰ 测试时间: 2025-11-09 12:57:29
🤖 LLM Provider: openrouter
📦 LLM Model: google/gemini-2.0-flash-exp:free
💾 Database: json
================================================================================

================================================================================
🧪 阶段 1: 测试 LLM 连接
================================================================================
✅ LLM Client 创建成功
   Provider: openrouter
   Model: google/gemini-2.0-flash-exp:free
   Base URL: https://openrouter.ai/api/v1

📡 测试 API 调用...
❌ LLM 连接失败: 429 Client Error: Too Many Requests for url: https://openrouter.ai/api/v1/chat/completions
Traceback (most recent call last):
  File "test_and_save_output.py", line 132, in main
    response = client.chat(messages)
  File ".\functions\llm_client.py", line 61, in chat
    return self._chat_openrouter(messages, temperature, max_tokens)
  File ".\functions\llm_client.py", line 97, in _chat_openrouter
    response.raise_for_status()
  File "C:\ProgramData\anaconda3\lib\site-packages\requests\models.py", line 939, in raise_for_status
    raise HTTPError(http_error_msg, response=self)
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests for url: https://openrouter.ai/api/v1/chat/completions


================================================================================
📁 阶段 2: 创建测试文件
================================================================================
✅ 测试文件已创建
   题目文件: test_data\questions.txt
   答案文件: test_data\001_张三_answers.txt
   评分标准: test_data\marking_scheme.txt

================================================================================
🚀 阶段 3: 运行完整批改工作流
================================================================================

❌ 工作流测试失败: No module named 'langgraph'
Traceback (most recent call last):
  File "test_and_save_output.py", line 161, in main
    from functions.langgraph.workflow_production import run_grading_workflow
  File ".\functions\langgraph\__init__.py", line 4, in <module>
    from .workflow import create_grading_workflow
  File ".\functions\langgraph\workflow.py", line 16, in <module>
    from langgraph.graph import StateGraph, END
ModuleNotFoundError: No module named 'langgraph'


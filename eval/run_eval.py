import json
import asyncio
import os
import sys

# Thêm thư mục ai_core vào sys.path để có thể import vlearn_ai
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ai_core')))

from vlearn_ai.interface import VLearnAICore
from langchain_google_genai import ChatGoogleGenerativeAI

async def run_eval():
    try:
        with open('eval/golden_set.json', 'r', encoding='utf-8') as f:
            golden_set = json.load(f)
    except Exception as e:
        print(f"Error loading golden set: {e}")
        return
    
    results = []
    correct_count = 0
    total = len(golden_set)

    print(f"Bắt đầu chạy đánh giá trên {total} test cases với LangGraph Core...")
    
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("Cảnh báo: GEMINI_API_KEY chưa được thiết lập!")
        
    # Khởi tạo model Gemini và truyền vào VLearnAICore
    gemini_model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.0
    )
    core = VLearnAICore(model=gemini_model)

    for idx, case in enumerate(golden_set):
        print(f"Testing [{idx+1}/{total}] {case['id']}...")
        
        try:
            # Tạo thread_id riêng cho từng case để không bị dính context cũ
            thread_id = f"eval_thread_{case['id']}"
            
            # Gọi trực tiếp qua SDK (không qua mạng)
            res = await core.start_turn(
                thread_id=thread_id,
                question=case["question"],
                selected_context=f"Slide content for page {case.get('page_number', 1)}"
            )
            
            # Lấy route thực tế từ kết quả
            route_dict = res.get("route")
            actual_route = route_dict.get("name") if route_dict else "unknown"
            
            expected = case["expected_route"]
            
            # Đánh giá Logic
            passed = False
            if actual_route == expected:
                passed = True
            elif actual_route == "followup" and expected in ["deep", "followup"]:
                passed = True
            elif actual_route == "grounded_answer" and expected == "simple":
                passed = True
                
            if passed:
                correct_count += 1
                
            results.append({
                "ID": case["id"],
                "Question": case["question"].replace('\n', ' '),
                "Expected": expected,
                "Actual": actual_route,
                "Pass": "✅ PASS" if passed else "❌ FAIL"
            })
            
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            print(f"Error on {case['id']}: {e}")
            with open("eval/errors.log", "a", encoding="utf-8") as err_f:
                err_f.write(f"--- Error on {case['id']} ---\n{err_msg}\n")
            results.append({
                "ID": case["id"],
                "Question": case["question"].replace('\n', ' '),
                "Expected": case["expected_route"],
                "Actual": "ERROR",
                "Pass": "❌ FAIL",
                "Notes": str(e).replace('\n', ' ')[:100] + '...' # truncate error message
            })
            
        # Thêm sleep để tránh lỗi 429 Rate Limit (Free Tier chỉ cho 15 request/phút)
        # LangGraph gọi LLM khoảng 2-3 lần cho mỗi câu hỏi -> mỗi câu hỏi tốn 2-3 requests.
        # Để an toàn (dưới 15 req/phút), cần nghỉ khoảng 12-15s giữa các câu hỏi.
        print("Sleeping 15s to avoid rate limit...")
        await asyncio.sleep(15)
            
    print("\nWriting results to eval_results.md...")
    with open('eval/eval_results.md', 'w', encoding='utf-8') as f:
        f.write("# Bảng Kết Quả Đánh Giá VLearn Tutor (Native LangGraph Engine)\n\n")
        f.write(f"**Kết quả: {correct_count} / {total} ({(correct_count/total)*100:.1f}%)**\n\n")
        f.write("| ID | Question | Expected Route | Actual Route | Pass/Fail | Notes |\n")
        f.write("|---|---|---|---|---|---|\n")
        
        for r in results:
            notes = r.get("Notes", "")
            f.write(f"| {r['ID']} | {r['Question']} | {r['Expected']} | {r['Actual']} | {r['Pass']} | {notes} |\n")
            
    print(f"\nEval completed! Result: {correct_count}/{total} ({(correct_count/total)*100:.1f}%).")

if __name__ == '__main__':
    asyncio.run(run_eval())

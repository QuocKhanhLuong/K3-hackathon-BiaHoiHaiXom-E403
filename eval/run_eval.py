import json
import requests
import time
import os
def run_eval():
    try:
        with open('eval/golden_set.json', 'r', encoding='utf-8') as f:
            golden_set = json.load(f)
    except Exception as e:
        print(f"Error loading golden set: {e}")
        return
    
    results = []
    correct_count = 0
    total = len(golden_set)

    print(f"Bắt đầu chạy đánh giá trên {total} test cases...")

    for case in golden_set:
        print(f"Testing {case['id']}...")
        payload = {
            "question": case["question"],
            "page_number": case.get("page_number", 1),
            "api_key": os.environ.get("GEMINI_API_KEY", "")
        }
        
        try:
            res = requests.post("http://localhost:8000/api/tutor/ask", json=payload, timeout=30)
            data = res.json()
            
            actual_route = data.get("orchestrator", {}).get("branch", "unknown")
            # Nếu expected_route là 'simple' thì actual cũng có thể là 'simple' hoặc 'grounded' tùy cấu trúc
            expected = case["expected_route"]
            
            if actual_route == expected:
                passed = True
            elif actual_route == "followup" and expected in ["deep", "followup"]:
                passed = True
            elif actual_route == "grounded_answer" and expected == "simple":
                passed = True
            else:
                passed = False
                
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
            print(f"Error on {case['id']}: {e}")
            results.append({
                "ID": case["id"],
                "Question": case["question"].replace('\n', ' '),
                "Expected": case["expected_route"],
                "Actual": "ERROR",
                "Pass": "❌ FAIL"
            })
            
        # Nghỉ 0.5 giây để tránh Rate Limit API
        time.sleep(0.5)
        
    print("Writing results to eval_results.md...")
    with open('eval/eval_results.md', 'w', encoding='utf-8') as f:
        f.write("# Bảng Kết Quả Đánh Giá VLearn Tutor (Run thật 100%)\n\n")
        f.write(f"**Kết quả: {correct_count} / {total} ({(correct_count/total)*100:.1f}%)**\n\n")
        f.write("| ID | Question | Expected Route | Actual Route | Pass/Fail |\n")
        f.write("|---|---|---|---|---|\n")
        
        for r in results:
            f.write(f"| {r['ID']} | {r['Question']} | {r['Expected']} | {r['Actual']} | {r['Pass']} |\n")
            
    print(f"\nEval completed! Result: {correct_count}/{total} ({(correct_count/total)*100:.1f}%).")

if __name__ == '__main__':
    run_eval()

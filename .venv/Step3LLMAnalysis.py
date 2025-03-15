# Step3LLMAnalysis.py

import pandas as pd
import os

# 비교할 파일 로드 (이전 단계에서 생성한 파일 활용)
base_dir = os.path.dirname(os.path.abspath(__file__))
comparison_file = os.path.join(base_dir, "comparison_result2.xlsx")
output_file = os.path.join(base_dir, "comparison_result3.xlsx")  # 자연어 분석 결과 저장 파일명

def generate_natural_language_summary(change_type, std_text, proj_text, diff_text):
    """변경 사항을 자연어로 설명"""
    if change_type == "추가됨":
        return f"이 문장이 새롭게 추가되었습니다: '{proj_text}'"
    elif change_type == "삭제됨":
        return f"이 문장이 삭제되었습니다: '{std_text}'"
    elif change_type == "변경됨":
        return f"이 문장은 다음과 같이 변경되었습니다: '{std_text}' → '{proj_text}'. 변경된 부분: {diff_text}"
    else:
        return "변경 없음"

# 데이터 로드
df = pd.read_excel(comparison_file)

# 자연어 설명 추가
df["자연어 설명"] = df.apply(lambda row: generate_natural_language_summary(
    row["변경 유형"], row["표준 사양서"], row["프로젝트 사양서"], row["변경된 부분"]
), axis=1)

# 비교 결과 저장
df.to_excel(output_file, index=False)

print(f"✅ LLM 기반 자연어 설명이 추가된 비교 보고서가 '{output_file}' 파일로 저장되었습니다!")

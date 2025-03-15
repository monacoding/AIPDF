# Step2Analysis.py

import difflib
import Levenshtein
import pandas as pd
import re
import os

# 비교할 파일 로드 (이전 단계에서 생성한 파일 활용)
base_dir = "/Users/gimtaehyeong/Desktop/코딩/개발/AIPDF"
comparison_file = os.path.join(base_dir, ".venv/comparison_result.xlsx")
output_file = os.path.join(base_dir, ".venv/comparison_result2.xlsx")  # 비교 결과 저장 파일명

# 데이터 로드
df = pd.read_excel(comparison_file)

# 비교 결과를 저장할 리스트
differences = []

# difflib을 사용한 문장 비교 함수
def get_diff(std_text, proj_text):
    differ = difflib.ndiff(std_text.split(), proj_text.split())
    changes = [word for word in differ if word.startswith("+") or word.startswith("-")]
    return " ".join(changes)

# Levenshtein 거리 계산 함수
def get_similarity(std_text, proj_text):
    return Levenshtein.ratio(std_text, proj_text)

# 비교 실행
for index, row in df.iterrows():
    std_text = row["표준 사양서"] if pd.notna(row["표준 사양서"]) else ""
    proj_text = row["프로젝트 사양서"] if pd.notna(row["프로젝트 사양서"]) else ""
    
    # 유사도 분석
    similarity = get_similarity(std_text, proj_text)
    
    # 변경 감지
    changes = get_diff(std_text, proj_text)
    
    # 추가/삭제/변경 여부 구분
    change_type = ""
    if not std_text and proj_text:
        change_type = "추가됨"
    elif std_text and not proj_text:
        change_type = "삭제됨"
    elif similarity < 0.85:
        change_type = "변경됨"
    else:
        change_type = "유사"
    
    differences.append({
        "표준 사양서": std_text,
        "프로젝트 사양서": proj_text,
        "변경 유형": change_type,
        "변경된 부분": changes,
        "유사도": round(similarity, 2)
    })

# 비교 결과 DataFrame 생성
df_comparison = pd.DataFrame(differences)

# 비교 결과 저장
df_comparison.to_excel(output_file, index=False)

print(f"✅ 텍스트 비교 완료! 결과가 '{output_file}' 파일로 저장되었습니다!")
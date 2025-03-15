# main.py

import fitz  # PyMuPDF
import pandas as pd
import re
import os

# PDF 파일 경로 설정 (절대 경로 사용)
base_dir = os.path.dirname(os.path.abspath(__file__))
std_spec_path = "/Users/gimtaehyeong/Desktop/코딩/개발/AIPDF/DB/SPEC/STD_SPEC.pdf"
proj_spec_path = "/Users/gimtaehyeong/Desktop/코딩/개발/AIPDF/DB/SPEC/3441_SPEC.pdf"
output_file = os.path.join(base_dir, "comparison_result.xlsx")  # 비교 결과 저장 파일명

def extract_text_from_pdf(pdf_path):
    """PDF에서 텍스트 추출"""
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text("text") + "\n"
    return text

# 표준 사양서와 프로젝트 사양서의 텍스트 추출
std_spec_text = extract_text_from_pdf(std_spec_path)
proj_spec_text = extract_text_from_pdf(proj_spec_path)

def split_into_paragraphs(text):
    """텍스트를 문단 단위로 분리"""
    paragraphs = re.split(r'\n\s*\n', text.strip())  # 빈 줄을 기준으로 분리
    paragraphs = [p.strip() for p in paragraphs if p.strip()]  # 공백 제거 후 필터링
    return paragraphs

# 문단 단위로 분리
std_paragraphs = split_into_paragraphs(std_spec_text)
proj_paragraphs = split_into_paragraphs(proj_spec_text)

def extract_added_sentences(std_text, proj_text):
    """표준 사양서 대비 프로젝트 사양서에서 추가된 문장만 추출"""
    std_sentences = set(re.split(r'(?<=[.!?])\s+', std_text))
    proj_sentences = re.split(r'(?<=[.!?])\s+', proj_text)
    added_sentences = [sent for sent in proj_sentences if sent not in std_sentences]  # 추가된 문장만 필터링
    return " ".join(added_sentences) if added_sentences else ""

# 비교 결과 저장을 위한 리스트
differences = []
max_length = max(len(std_paragraphs), len(proj_paragraphs))

# 문단 단위 비교 수행
for i in range(max_length):
    std_text = std_paragraphs[i] if i < len(std_paragraphs) else ""
    proj_text = proj_paragraphs[i] if i < len(proj_paragraphs) else ""
    added_content = extract_added_sentences(std_text, proj_text)
    
    differences.append({
        "표준 사양서": std_text,
        "프로젝트 사양서": proj_text,
        "추가된 내용": added_content
    })

# 비교 결과를 DataFrame으로 정리
df_comparison = pd.DataFrame(differences)

# 비교 결과 저장
df_comparison.to_excel(output_file, index=False)

print(f"✅ 비교 보고서가 '{output_file}' 파일로 저장되었습니다! 문단 단위로 비교되었으며, 추가된 문장만 3열에 포함되었습니다.")
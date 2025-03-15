# Step4GenerateReport.py

import pandas as pd
import os
from fpdf import FPDF

# 📌 폰트 및 파일 경로 설정
base_dir = os.path.dirname(os.path.abspath(__file__))
font_path = "/Users/gimtaehyeong/Desktop/코딩/개발/AIPDF/.venv/fonts/NanumGothic.ttf"
comparison_file = os.path.join(base_dir, "comparison_result3.xlsx")
output_pdf = os.path.join(base_dir, "comparison_report.pdf")

# 📌 폰트 파일이 존재하는지 확인
if not os.path.exists(font_path):
    raise FileNotFoundError(f"❌ 폰트 파일을 찾을 수 없습니다: {font_path}")

# 데이터 로드
df = pd.read_excel(comparison_file)

# 📌 PDF 생성 클래스 (보고서 스타일 적용)
class PDF(FPDF):
    def header(self):
        self.set_font("NanumGothic", "", 16)
        self.cell(200, 10, "LNG 사양 비교 보고서", ln=True, align="C")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("NanumGothic", "", 10)
        self.cell(0, 10, f"페이지 {self.page_no()}", align="C")

# 📌 PDF 보고서 생성 함수 (줄바꿈 + 행 높이 맞춤 + 열 정렬 개선)
def generate_pdf_report(dataframe, output_path):
    pdf = PDF(orientation="L", unit="mm", format="A4")  # 가로 방향 A4 설정
    pdf.set_auto_page_break(auto=True, margin=15)

    # 📌 한글 폰트 등록
    pdf.add_font("NanumGothic", "", font_path, uni=True)

    # 📌 표지 추가
    pdf.add_page()
    pdf.set_font("NanumGothic", "", 24)
    pdf.cell(0, 20, "LNG 사양 비교 보고서", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("NanumGothic", "", 14)
    pdf.cell(0, 10, "작성 날짜: 2024년 3월 16일", ln=True, align="C")
    pdf.cell(0, 10, "작성자: 홍길동", ln=True, align="C")
    pdf.cell(0, 10, "프로젝트: LNG Carrier 3441", ln=True, align="C")
    pdf.ln(20)

    # 📌 본문 페이지 추가 (표 형식 적용)
    pdf.add_page()
    pdf.set_font("NanumGothic", "", 12)

    col_widths = [50, 50, 30, 65, 65]  # 각 컬럼 너비 설정

    # 📌 표 헤더 작성
    pdf.set_fill_color(200, 220, 255)  # 연한 파란색 배경
    headers = ["표준 사양서", "프로젝트 사양서", "변경 유형", "변경된 부분", "자연어 설명"]
    for i in range(len(headers)):
        pdf.cell(col_widths[i], 10, headers[i], border=1, align="C", fill=True)
    pdf.ln()

    # 📌 데이터 입력 (🔹 모든 열 높이를 맞추기 위해 가장 긴 열을 기준으로 줄 수 계산)
    for _, row in dataframe.iterrows():
        cell_texts = [
            str(row["표준 사양서"]),
            str(row["프로젝트 사양서"]),
            str(row["변경 유형"]),
            str(row["변경된 부분"]),
            str(row["자연어 설명"]),
        ]
        
        # 📌 각 열의 줄 수를 맞추기 위해 가장 긴 셀의 줄 개수 계산
        line_counts = [pdf.get_string_width(text) // col_widths[i] + 1 for i, text in enumerate(cell_texts)]
        max_lines = max(line_counts)  # 가장 긴 셀 기준으로 행 높이 설정

        y_start = pdf.get_y()  # 현재 Y 좌표 저장

        # 📌 각 열을 동일한 높이로 맞춰 출력
        for i, text in enumerate(cell_texts):
            x_start = pdf.get_x()  # 현재 X 좌표 저장
            pdf.multi_cell(col_widths[i], 8, text, border=1, align="L")  # multi_cell 적용
            pdf.set_xy(x_start + col_widths[i], y_start)  # 다음 열의 위치로 이동

        pdf.ln(8 * max_lines)  # 가장 긴 줄 기준으로 행 높이 맞추기

    pdf.output(output_path, "F")

# 📌 PDF 보고서 생성
generate_pdf_report(df, output_pdf)

print(f"✅ 최종 보고서가 '{output_pdf}' 파일로 저장되었습니다! (줄바꿈 문제 + 행 높이 균일화 + 열 정렬 개선 완료)")
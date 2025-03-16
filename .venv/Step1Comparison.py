from flask import Flask, request, render_template_string, send_file
import fitz  # PyMuPDF
import re
import os
import difflib
from datetime import datetime

app = Flask(__name__)

# 📌 표준 사양서 경로 (현재는 동일 경로 사용, 나중에 선종별로 수정 가능)
std_spec_path = "/Users/gimtaehyeong/Desktop/코딩/개발/AIPDF/DB/SPEC/STD_SPEC_2.pdf"

# 📌 선종 목록 정의
ship_types = {
    "1": ("174K LNGC", std_spec_path),
    "2": ("180K LNGC", std_spec_path),
    "3": ("200K LNGC", std_spec_path),
    "4": ("88K LPGC", std_spec_path),
    "5": ("91K LPGC", std_spec_path)
}

# 📌 업로드 디렉토리 설정
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route("/", methods=["GET", "POST"])
def compare_specs():
    if request.method == "POST":
        # 선종 선택
        selected_ship = request.form.get("ship_type")
        if not selected_ship or selected_ship not in ship_types:
            return "선종을 선택해주세요.", 400
        
        ship_type_name, selected_std_spec_path = ship_types[selected_ship]
        
        # 파일 업로드
        if "proj_spec" not in request.files:
            return "프로젝트 사양서를 업로드해주세요.", 400
        
        proj_spec_file = request.files["proj_spec"]
        if proj_spec_file.filename == "":
            return "프로젝트 사양서를 업로드해주세요.", 400
        
        proj_spec_path = os.path.join(UPLOAD_FOLDER, proj_spec_file.filename)
        proj_spec_file.save(proj_spec_path)

        # 텍스트 추출
        std_spec_text = extract_text_from_pdf(selected_std_spec_path)
        proj_spec_text = extract_text_from_pdf(proj_spec_path)

        if std_spec_text is None or proj_spec_text is None:
            return "PDF 파일 처리 중 오류가 발생했습니다.", 500

        # 문단 분리
        std_paragraphs = split_into_paragraphs(std_spec_text)
        proj_paragraphs = split_into_paragraphs(proj_spec_text)

        # 비교 결과 생성
        differences = []
        similarity_threshold = 0.85

        for std_text in std_paragraphs:
            best_match, similarity_score = find_best_matching_paragraph(std_text, proj_paragraphs, similarity_threshold)
            
            if similarity_score > similarity_threshold:
                diff_text = highlight_differences(std_text, best_match)
                if not diff_text:
                    continue
            else:
                diff_text = f"📌 새로운 문단 추가됨: {best_match}" if best_match else ""
            
            differences.append({
                "표준 사양서": std_text,
                "프로젝트 사양서": best_match,
                "비교 결과": diff_text if diff_text else best_match
            })

        # HTML 결과 생성
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Comparison Result</title>
            <style>
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th, td {{
                    border: 1px solid black;
                    padding: 8px;
                    text-align: left;
                    vertical-align: top;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
            </style>
        </head>
        <body>
            <h1>Comparison Result</h1>
            <h2>선종: {ship_type_name}</h2>
            <table>
                <tr>
                    <th>표준 사양서</th>
                    <th>프로젝트 사양서</th>
                    <th>비교 결과</th>
                </tr>
        """
        for diff in differences:
            html_content += f"""
                <tr>
                    <td>{diff['표준 사양서']}</td>
                    <td>{diff['프로젝트 사양서']}</td>
                    <td>{diff['비교 결과']}</td>
                </tr>
            """
        html_content += """
            </table>
            <br><a href="/">다시 비교하기</a>
        </body>
        </html>
        """

        # 결과 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(UPLOAD_FOLDER, f"comparison_result_{ship_type_name}_{timestamp}.html")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return send_file(output_file, as_attachment=False)

    # GET 요청 시 기본 페이지 렌더링
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>사양서 비교</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            label { margin-right: 10px; }
            select, input[type="file"], input[type="submit"] { margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>사양서 비교</h1>
        <form method="post" enctype="multipart/form-data">
            <label for="ship_type">선종 선택:</label>
            <select name="ship_type" id="ship_type" required>
                <option value="">선종을 선택하세요</option>
                {% for key, value in ship_types.items() %}
                    <option value="{{ key }}">{{ key }}. {{ value[0] }}</option>
                {% endfor %}
            </select><br>
            <label for="proj_spec">프로젝트 사양서 업로드:</label>
            <input type="file" name="proj_spec" id="proj_spec" accept=".pdf" required><br>
            <input type="submit" value="비교 시작">
        </form>
    </body>
    </html>
    """, ship_types=ship_types)

def extract_text_from_pdf(pdf_path):
    """PDF에서 텍스트 추출"""
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text("text") + "\n"
    except Exception as e:
        print(f"❌ 오류: {pdf_path} 파일을 처리하는 중 문제가 발생했습니다. ({str(e)})")
        return None
    return text

def split_into_paragraphs(text):
    """텍스트를 문단 단위로 분리"""
    paragraphs = re.split(r'\n\s*\n', text.strip())
    return [p.strip() for p in paragraphs if p.strip()]

def find_best_matching_paragraph(std_paragraph, proj_paragraphs, threshold=0.85):
    """표준 사양서의 문단과 가장 유사한 프로젝트 사양서 문단을 찾음"""
    best_match = ""
    best_score = 0.0
    for proj_paragraph in proj_paragraphs:
        similarity = difflib.SequenceMatcher(None, std_paragraph, proj_paragraph).ratio()
        if similarity > best_score:
            best_score = similarity
            best_match = proj_paragraph
    return best_match, best_score

def highlight_differences(std_text, proj_text):
    """문장 간 차이점을 단어 단위로 비교하여 HTML 태그로 스타일 적용"""
    diff = list(difflib.ndiff(std_text.split(), proj_text.split()))
    highlighted_text = []
    for word in diff:
        if word.startswith("+ "):
            highlighted_text.append(f'<span style="color: red; font-weight: bold;">{word[2:]}</span>')
        elif word.startswith("- "):
            highlighted_text.append(f'<span style="text-decoration: line-through;">{word[2:]}</span>')
        else:
            highlighted_text.append(word[2:] if word.startswith("  ") else word)
    return " ".join(highlighted_text) if highlighted_text else ""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
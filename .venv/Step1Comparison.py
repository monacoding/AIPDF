from flask import Flask, request, render_template_string, send_file
import fitz  # PyMuPDF
import re
import os
import difflib
from datetime import datetime
import requests
from dotenv import load_dotenv

app = Flask(__name__)

# 📌 .env 파일에서 환경 변수 로드 (절대 경로로 명시)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

# 📌 OpenAI API 설정
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo"

# API 키 디버깅
print(f"📌 Loaded OPENAI_API_KEY: {OPENAI_API_KEY if OPENAI_API_KEY else 'Not found'}")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일 또는 환경 변수를 확인하세요.")

# 📌 표준 사양서 경로
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

def generate_report(differences):
    """OpenAI API를 사용해 Word 양식에 맞춘 보고서를 생성"""
    diff_text = ""
    for i, diff in enumerate(differences, 1):
        diff_text += f"차이점 {i}:\n"
        diff_text += f"- 표준 사양서: {diff['표준 사양서']}\n"
        diff_text += f"- 프로젝트 사양서: {diff['프로젝트 사양서']}\n"
        diff_text += f"- 차이점: {diff['비교 결과']}\n\n"

    report_template = """
    [제목]
    사양서 비교 보고서

    [개요]
    본 보고서는 표준 사양서와 프로젝트 사양서 간 차이점을 분석하고, 그 의도를 설명합니다.

    [차이점 분석]
    {diff_analysis}

    [결론]
    차이점의 주요 의도와 프로젝트에 미치는 영향을 요약합니다.
    """

    messages = [
        {"role": "system", "content": "당신은 사양서 비교 전문가입니다. 아래 Word 양식에 따라 차이점을 한국어로 분석하고 의도를 설명하는 보고서를 작성해주세요."},
        {"role": "user", "content": f"""
        아래는 표준 사양서와 프로젝트 사양서의 비교 결과입니다. 다음 Word 양식에 따라 보고서를 작성해주세요:

        {report_template}

        비교 결과:
        {diff_text}
        """}
    ]

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY.strip()}",  # 공백 제거
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.7
    }
    try:
        print(f"📌 Sending request to OpenAI with headers: {headers}")
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ OpenAI API 호출 중 오류: {str(e)}")
        return "보고서 생성 중 오류가 발생했습니다. API 키 또는 네트워크를 확인해주세요."

@app.route("/", methods=["GET", "POST"])
def compare_specs():
    if request.method == "POST":
        selected_ship = request.form.get("ship_type")
        if not selected_ship or selected_ship not in ship_types:
            return "선종을 선택해주세요.", 400
        
        ship_type_name, selected_std_spec_path = ship_types[selected_ship]
        
        if "proj_spec" not in request.files:
            return "프로젝트 사양서를 업로드해주세요.", 400
        
        proj_spec_file = request.files["proj_spec"]
        if proj_spec_file.filename == "":
            return "프로젝트 사양서를 업로드해주세요.", 400
        
        proj_spec_path = os.path.join(UPLOAD_FOLDER, proj_spec_file.filename)
        proj_spec_file.save(proj_spec_path)

        std_spec_text = extract_text_from_pdf(selected_std_spec_path)
        proj_spec_text = extract_text_from_pdf(proj_spec_path)

        if std_spec_text is None or proj_spec_text is None:
            return "PDF 파일 처리 중 오류가 발생했습니다.", 500

        std_paragraphs = split_into_paragraphs(std_spec_text)
        proj_paragraphs = split_into_paragraphs(proj_spec_text)

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

        report = generate_report(differences)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Comparison Result</title>
            <style>
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid black; padding: 8px; text-align: left; vertical-align: top; }}
                th {{ background-color: #f2f2f2; }}
                .report {{ margin-top: 20px; padding: 10px; border: 1px solid #ccc; white-space: pre-wrap; }}
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
        html_content += f"""
            </table>
            <div class="report">
                <h3>비교 보고서</h3>
                <p>{report}</p>
            </div>
            <br><a href="/">다시 비교하기</a>
        </body>
        </html>
        """

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(UPLOAD_FOLDER, f"comparison_result_{ship_type_name}_{timestamp}.html")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return send_file(output_file, as_attachment=False)

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
    paragraphs = re.split(r'\n\s*\n', text.strip())
    return [p.strip() for p in paragraphs if p.strip()]

def find_best_matching_paragraph(std_paragraph, proj_paragraphs, threshold=0.85):
    best_match = ""
    best_score = 0.0
    for proj_paragraph in proj_paragraphs:
        similarity = difflib.SequenceMatcher(None, std_paragraph, proj_paragraph).ratio()
        if similarity > best_score:
            best_score = similarity
            best_match = proj_paragraph
    return best_match, best_score

def highlight_differences(std_text, proj_text):
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
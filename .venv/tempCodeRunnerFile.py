from flask import Flask, request, render_template_string, send_file
import fitz  # PyMuPDF
import re
import os
import difflib
from datetime import datetime
import requests
from dotenv import load_dotenv

app = Flask(__name__)

# 📌 .env 파일에서 환경 변수 로드
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

# 📌 OpenAI API 설정
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo"

# 📌 표준 사양서 경로
std_spec_path = "/Users/gimtaehyeong/Desktop/코딩/개발/AIPDF/DB/SPEC/STD_SPEC_3.pdf"

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
    [차이점 분석]
    {diff_analysis}
    """

    messages = [
        {"role": "system", "content": "당신은 사양서 비교 전문가입니다. 아래 Word 양식에 따라 차이점만 한국어로 분석하고 의도를 설명하는 보고서를 작성해주세요. 제목과 개요는 포함하지 마세요."},
        {"role": "user", "content": f"""
        아래는 표준 사양서와 프로젝트 사양서의 비교 결과입니다. 다음 Word 양식에 따라 보고서를 작성해주세요:

        {report_template}

        비교 결과:
        {diff_text}
        """}
    ]

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY.strip()}",
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

def group_by_section(paragraphs):
    """문단을 섹션 단위로 그룹화"""
    sections = []
    current_section = None
    section_paragraphs = []

    section_pattern = re.compile(r'^\d+\.\d+\s+.*$')  # 섹션 넘버 패턴 (예: 5.6 WATER BALLAST SYSTEM)

    for para in paragraphs:
        if para.strip():  # 빈 문자열 제외
            if section_pattern.match(para):
                if current_section:  # 이전 섹션 저장
                    sections.append((current_section, section_paragraphs))
                current_section = para
                section_paragraphs = []
            else:
                section_paragraphs.append(para)

    if current_section:  # 마지막 섹션 저장
        sections.append((current_section, section_paragraphs))

    return sections if sections else [(None, paragraphs)]  # 섹션이 없는 경우 전체 문단 반환

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

        # 섹션별로 그룹화
        std_sections = group_by_section(std_paragraphs)
        proj_sections = group_by_section(proj_paragraphs)

        differences = []
        similarity_threshold = 0.5

        # 섹션 단위 비교
        section_differences = []  # 섹션별 차이점 저장

        # 표준 사양서 섹션 기준으로 비교
        for std_section, std_section_paras in std_sections:
            # 동일 섹션 찾기 (섹션 제목이 동일한 경우)
            proj_section = None
            proj_section_paras = []
            for p_section, p_paras in proj_sections:
                if p_section == std_section:
                    proj_section = p_section
                    proj_section_paras = p_paras
                    break

            section_diffs = []
            # 섹션 내 문단 비교 (빈 섹션 처리)
            if std_section_paras or proj_section_paras:  # 섹션에 문단이 있는 경우만 비교
                for std_text in std_section_paras:
                    best_match, similarity_score = find_best_matching_paragraph(std_text, proj_section_paras, similarity_threshold)
                    print(f"📌 비교: std_text='{std_text}', best_match='{best_match}', similarity={similarity_score}")
                    
                    if best_match:
                        diff_text = highlight_differences(std_text, best_match)
                        if diff_text:
                            section_diffs.append({
                                "표준 사양서": std_text,
                                "프로젝트 사양서": best_match,
                                "비교 결과": diff_text
                            })
                    else:
                        section_diffs.append({
                            "표준 사양서": std_text,
                            "프로젝트 사양서": "",
                            "비교 결과": "📌 표준 사양서에만 존재"
                        })

                # 프로젝트 사양서에만 있는 문단 확인
                processed_proj_paragraphs = set(diff["프로젝트 사양서"] for diff in section_diffs if diff["프로젝트 사양서"])
                for proj_text in proj_section_paras:
                    if proj_text not in processed_proj_paragraphs and proj_text:
                        section_diffs.append({
                            "표준 사양서": "",
                            "프로젝트 사양서": proj_text,
                            "비교 결과": f'<span class="added">{proj_text}</span>'
                        })

            if section_diffs:  # 차이점이 있는 경우 섹션 추가
                section_differences.append((std_section, section_diffs))
                differences.extend(section_diffs)

        # 표준 사양서에 없는 프로젝트 사양서 섹션 확인
        processed_std_sections = set(section for section, _ in std_sections if section)
        for proj_section, proj_section_paras in proj_sections:
            if proj_section not in processed_std_sections and proj_section:
                section_diffs = []
                for proj_text in proj_section_paras:
                    section_diffs.append({
                        "표준 사양서": "",
                        "프로젝트 사양서": proj_text,
                        "비교 결과": f'<span class="added">{proj_text}</span>'
                    })
                section_differences.append((proj_section, section_diffs))
                differences.extend(section_diffs)

        report = generate_report(differences)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>현대중공업 선장설계부 호선 사양서 비교 프로그램</title>
            <!-- Bootstrap 5 CDN -->
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{
                    background-color: #f8f9fa;
                    font-family: 'Noto Sans KR', sans-serif;
                }}
                .header {{
                    background-color: #28a745; /* 초록색 */
                    color: white;
                    padding: 20px;
                    text-align: center;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .container {{
                    max-width: 1200px;
                    margin: 40px auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                }}
                .form-section {{
                    margin-bottom: 30px;
                }}
                .section-card {{
                    margin-bottom: 30px;
                    border: 1px solid #e9ecef;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .section-header {{
                    background-color: #e9ecef;
                    padding: 15px;
                    font-size: 1.2em;
                    font-weight: bold;
                }}
                .table {{
                    margin-bottom: 0;
                }}
                .table th {{
                    background-color: #f1f3f5;
                    color: #343a40;
                }}
                .table td {{
                    vertical-align: middle;
                    padding: 12px;
                    border-bottom: 1px solid #dee2e6;
                }}
                .report {{
                    margin-top: 40px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    white-space: pre-wrap;
                }}
                .added {{ color: #dc3545; font-weight: bold; }}
                .deleted {{ text-decoration: line-through; }}
                .btn-primary {{
                    background-color: #003087;
                    border-color: #003087;
                    transition: background-color 0.3s;
                }}
                .btn-primary:hover {{
                    background-color: #0056b3;
                    border-color: #0056b3;
                }}
                .file-name {{
                    margin-top: 10px;
                    font-style: italic;
                    color: #6c757d;
                }}
                @media print {{
                    .container {{
                        box-shadow: none;
                        margin: 0;
                        padding: 20px;
                    }}
                    .btn-primary, .file-name {{
                        display: none;
                    }}
                }}
            </style>
            <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap" rel="stylesheet">
        </head>
        <body>
            <div class="header">
                <h1>현대중공업 선장설계부 호선 사양서 비교 프로그램</h1>
            </div>
            <div class="container">
                <h2 class="mb-4">비교 결과: 선종 - {ship_type_name}</h2>
                <div class="form-section">
                    <p class="file-name">업로드된 파일: {proj_spec_file.filename}</p>
                </div>
        """

        # 섹션별로 카드 생성
        for section_title, section_diffs in section_differences:
            if section_title or section_diffs:  # 유효한 섹션만 표시
                html_content += f"""
                    <div class="section-card">
                        <div class="section-header">{section_title if section_title else 'Unnamed Section'}</div>
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th>표준 사양서</th>
                                    <th>프로젝트 사양서</th>
                                    <th>비교 결과</th>
                                </tr>
                            </thead>
                            <tbody>
                """
                for diff in section_diffs:
                    html_content += f"""
                                <tr>
                                    <td>{diff['표준 사양서'] if diff['표준 사양서'] else '-'}</td>
                                    <td>{diff['프로젝트 사양서'] if diff['프로젝트 사양서'] else '-'}</td>
                                    <td>{diff['비교 결과'] if diff['비교 결과'] else '-'}</td>
                                </tr>
                    """
                html_content += """
                            </tbody>
                        </table>
                    </div>
                """

        html_content += f"""
                <div class="report">
                    <h3 class="mb-3">비교 보고서</h3>
                    <p>{report}</p>
                </div>
                <div class="mt-4">
                    <a href="/" class="btn btn-primary me-2">다시 비교하기</a>
                    <button class="btn btn-secondary" onclick="window.print()">출력</button>
                </div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
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
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>현대중공업 선장설계부 호선 사양서 비교 프로그램</title>
        <!-- Bootstrap 5 CDN -->
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background-color: #f8f9fa;
                font-family: 'Noto Sans KR', sans-serif;
            }
            .header {
                background-color: #28a745; /* 초록색 */
                color: white;
                padding: 20px;
                text-align: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .container {
                max-width: 1200px;
                margin: 40px auto;
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
            .btn-primary {
                background-color: #003087;
                border-color: #003087;
                transition: background-color 0.3s;
            }
            .btn-primary:hover {
                background-color: #0056b3;
                border-color: #0056b3;
            }
            .form-section {
                margin-bottom: 30px;
            }
            .file-name {
                margin-top: 10px;
                font-style: italic;
                color: #6c757d;
            }
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Noto Sans+KR:wght@400;700&display=swap" rel="stylesheet">
    </head>
    <body>
        <div class="header">
            <h1>현대중공업 선장설계부 호선 사양서 비교 프로그램</h1>
        </div>
        <div class="container">
            <div class="form-section">
                <form method="post" enctype="multipart/form-data">
                    <div class="mb-3">
                        <label for="ship_type" class="form-label">선종 선택:</label>
                        <select name="ship_type" id="ship_type" class="form-select" required>
                            <option value="">선종을 선택하세요</option>
                            {% for key, value in ship_types.items() %}
                                <option value="{{ key }}">{{ key }}. {{ value[0] }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="proj_spec" class="form-label">프로젝트 사양서 업로드:</label>
                        <input type="file" name="proj_spec" id="proj_spec" class="form-control" accept=".pdf" required>
                        <div id="file-name" class="file-name">선택된 파일: 없음</div>
                    </div>
                    <button type="submit" class="btn btn-primary">비교 시작</button>
                </form>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            document.getElementById('proj_spec').addEventListener('change', function() {
                const fileName = this.files[0] ? this.files[0].name : '없음';
                document.getElementById('file-name').textContent = '선택된 파일: ' + fileName;
            });
        </script>
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
    if not std_text or not proj_text:
        return ""
    diff = list(difflib.ndiff(std_text.split(), proj_text.split()))
    highlighted_text = []
    for word in diff:
        if word.startswith("+ "):
            highlighted_text.append(f'<span class="added">{word[2:]}</span>')
        elif word.startswith("- "):
            highlighted_text.append(f'<span class="deleted">{word[2:]}</span>')
        else:
            highlighted_text.append(word[2:] if word.startswith("  ") else word)
    result = " ".join(highlighted_text)
    print(f"📌 Highlighted diff: {result}")
    return result if result else ""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
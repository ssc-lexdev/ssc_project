"""
음주운전 판결문 PDF → CSV 추출 프로그램
추출 항목: 주문, 사건, 검사, 판사, 변호인, 판결선고, 범죄사실, 양형이유
"""

import os
import re
import csv
from pathlib import Path

# ─── 경로 설정 ───────────────────────────────────────────────
SOURCE_DIR = r"Y:\2026SSC\assist\2nd - big data - yoon sung jin\음주운전 판결"
OUTPUT_DIR = r"Y:\2026SSC\assist\2nd - big data - yoon sung jin\pjt 음주운전 분석"
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "음주운전_판결문_추출.csv")


# ─── PDF 텍스트 추출 ──────────────────────────────────────────
def extract_text_from_pdf(pdf_path: str) -> str:
    """pdfplumber 우선, 실패 시 PyMuPDF(fitz) 사용"""
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except ImportError:
        pass

    try:
        import fitz  # PyMuPDF
        text = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text() + "\n"
        return text
    except ImportError:
        raise RuntimeError(
            "PDF 파싱 라이브러리가 없습니다.\n"
            "아래 명령어 중 하나로 설치하세요:\n"
            "  pip install pdfplumber\n"
            "  pip install pymupdf"
        )


# ─── 공통 유틸 ───────────────────────────────────────────────
def _clean(text: str) -> str:
    """연속 공백 정리 및 앞뒤 공백 제거"""
    return re.sub(r"\s+", " ", text).strip()


def _search(pattern: str, text: str, flags=re.DOTALL) -> str:
    """정규식 매칭 후 1번 그룹 반환. 없으면 빈 문자열"""
    m = re.search(pattern, text, flags)
    return _clean(m.group(1)) if m else ""


# ─── 필드별 추출 함수 ─────────────────────────────────────────
def extract_court(text: str) -> str:
    """법원명: 첫 10줄 안에서 '법원' 포함 라인 (출처 URL 제외)"""
    for line in text.split("\n")[:10]:
        line = line.strip()
        if "법원" in line and "lbox.kr" not in line and "출처" not in line:
            return line
    return ""


def extract_사건(text: str) -> str:
    return _search(r"사\s*건\s+(.+?)(?=피고인|검\s*사|변호인|판결선고|\n)", text)


def extract_검사(text: str) -> str:
    return _search(r"검\s*사\s+(.+?)(?=변호인|피고인|판결선고|\n)", text)


def extract_변호인(text: str) -> str:
    return _search(r"변\s*호\s*인\s+(.+?)(?=판결선고|검\s*사|\n)", text)


def extract_판결선고(text: str) -> str:
    return _search(r"판\s*결\s*선\s*고\s+(\d{4}[\.\s\d]+\.?)", text)


def extract_판사(text: str) -> str:
    # 마지막에 등장하는 "판사 이름" 패턴
    matches = re.findall(r"판\s*사\s+(\S+)", text)
    return matches[-1].strip() if matches else ""


def extract_주문(text: str) -> str:
    return _search(
        r"주\s*문\s*(.+?)(?=이\s*유|범\s*죄\s*사\s*실|양\s*형)",
        text
    )


def extract_범죄사실(text: str) -> str:
    # [범죄사실] 섹션만 추출 (범죄전력 제외)
    m = re.search(
        r"\[범\s*죄\s*사\s*실\]\s*(.+?)(?=증거의\s*요지|법령의\s*적용|양\s*형|판\s*사)",
        text, re.DOTALL
    )
    if m:
        return _clean(m.group(1))
    # 대괄호 없는 경우
    return _search(
        r"범\s*죄\s*사\s*실(.+?)(?=증거의\s*요지|법령의\s*적용|양\s*형|판\s*사)",
        text
    )


def extract_양형이유(text: str) -> str:
    return _search(
        r"양\s*형(?:의\s*)?이\s*유\s*(.+?)(?=판\s*사|$)",
        text
    )


# ─── 메인 처리 ───────────────────────────────────────────────
FIELDNAMES = ["파일명", "법원", "사건", "검사", "변호인", "판결선고", "판사", "주문", "범죄사실", "양형이유"]


def process_pdf(pdf_path: Path) -> dict:
    text = extract_text_from_pdf(str(pdf_path))
    return {
        "파일명":   pdf_path.name,
        "법원":     extract_court(text),
        "사건":     extract_사건(text),
        "검사":     extract_검사(text),
        "변호인":   extract_변호인(text),
        "판결선고": extract_판결선고(text),
        "판사":     extract_판사(text),
        "주문":     extract_주문(text),
        "범죄사실": extract_범죄사실(text),
        "양형이유": extract_양형이유(text),
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files = sorted(Path(SOURCE_DIR).glob("*.pdf"))
    if not pdf_files:
        print(f"PDF 파일이 없습니다: {SOURCE_DIR}")
        return

    print(f"총 {len(pdf_files)}개 파일 처리 시작\n")
    records = []

    for pdf_path in pdf_files:
        print(f"[처리] {pdf_path.name}")
        try:
            record = process_pdf(pdf_path)
            records.append(record)
            print(f"  사건: {record['사건']}")
            print(f"  판결선고: {record['판결선고']}  판사: {record['판사']}\n")
        except Exception as e:
            print(f"  !! 오류: {e}\n")
            records.append({f: (pdf_path.name if f == "파일명" else f"오류: {e}") for f in FIELDNAMES})

    # CSV 저장 (utf-8-sig → 엑셀에서 한글 깨짐 없음)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    print(f"[완료] CSV 저장 위치:\n  {OUTPUT_CSV}")
    print(f"  총 {len(records)}건 처리됨")


if __name__ == "__main__":
    main()

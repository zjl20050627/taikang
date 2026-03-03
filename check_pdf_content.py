import PyPDF2
import os

def extract_pdf_text(pdf_path):
    """提取PDF文件文本"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = []
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text.append(page.extract_text())
            return '\n'.join(text)
    except Exception as e:
        return f"Error extracting text: {str(e)}"

# 查看PDF文件
data_dir = 'data/raw/medical'
pdf_files = [f for f in os.listdir(data_dir) if f.endswith('.pdf')]

for pdf_file in pdf_files:
    pdf_path = os.path.join(data_dir, pdf_file)
    print(f"=== 查看文件: {pdf_file} ===")
    text = extract_pdf_text(pdf_path)
    # 打印前1000个字符，了解文件结构
    print(text[:1000])
    print("...")
    print(f"文件总长度: {len(text)} 字符")
    print("\n")

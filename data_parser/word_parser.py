import os
import hashlib
from typing import List
from .base_parser import BaseParser, DataBlock, ModalityType


class WordParser(BaseParser):
    """Word文件解析器

    将Word文件解析为数据块，保存到cache目录下。
    """
    def __init__(self, cache_dir: str = "cache/data_blocks"):
        super().__init__()
        self.supported_extensions = ['docx', 'doc']
        self.cache_dir = cache_dir

    def _get_cache_path(self, file_path: str) -> str:
        """生成缓存目录路径"""
        file_hash = hashlib.md5(os.path.abspath(file_path).encode()).hexdigest()[:12]
        file_name = os.path.splitext(os.path.basename(file_path))[0]

        cache_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            self.cache_dir,
            f"{file_name}_{file_hash}"
        )

        os.makedirs(cache_path, exist_ok=True)
        return cache_path

    def parse(self, file_path: str) -> List[DataBlock]:
        """解析Word文件"""
        if not self.can_parse(file_path):
            raise ValueError(f"Unsupported file format: {file_path}")

        ext = file_path.lower().split('.')[-1]

        if ext == 'doc':
            return self._parse_doc(file_path)
        else:
            return self._parse_docx(file_path)

    def _parse_docx(self, file_path: str) -> List[DataBlock]:
        """解析docx文件"""
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "python-docx is required for Word file parsing. "
                "Install it with: pip install python-docx"
            )

        blocks = []
        doc = Document(file_path)

        # 获取缓存目录
        cache_path = self._get_cache_path(file_path)

        # 解析段落
        for para_idx, paragraph in enumerate(doc.paragraphs):
            if paragraph.text.strip():
                # 保存文本到缓存
                text_cache_path = os.path.join(cache_path, f"text_{para_idx}.txt")
                try:
                    with open(text_cache_path, 'w', encoding='utf-8') as f:
                        f.write(paragraph.text)
                except Exception as e:
                    print(f"[WordParser] 保存文本缓存失败: {e}")
                    text_cache_path = None

                block = DataBlock(
                    block_id=self._generate_block_id(file_path, len(blocks)),
                    modality=ModalityType.TEXT,
                    addr=text_cache_path,
                    file_path=file_path,
                    metadata={
                        'source': 'python-docx',
                        'paragraph_index': para_idx,
                        'style': paragraph.style.name if paragraph.style else None
                    }
                )
                blocks.append(block)

        # 解析表格
        for table_idx, table in enumerate(doc.tables):
            table_data = []
            for row in table.rows:
                row_data = [cell.text for cell in row.cells]
                table_data.append(row_data)

            table_text = self._table_to_text(table_data)

            # 保存表格到缓存
            table_cache_path = os.path.join(cache_path, f"table_{table_idx}.txt")
            try:
                with open(table_cache_path, 'w', encoding='utf-8') as f:
                    f.write(table_text)
            except Exception as e:
                print(f"[WordParser] 保存表格缓存失败: {e}")
                table_cache_path = None

            block = DataBlock(
                block_id=self._generate_block_id(file_path, len(blocks)),
                modality=ModalityType.TABLE,
                addr=table_cache_path,
                file_path=file_path,
                metadata={
                    'source': 'python-docx',
                    'table_index': table_idx,
                    'rows': len(table_data),
                    'cols': len(table_data[0]) if table_data else 0
                }
            )
            blocks.append(block)

        # 解析图片
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                try:
                    image_data = rel.target_part.blob

                    # 保存图片到缓存
                    image_ext = rel.target_ref.split('.')[-1] if '.' in rel.target_ref else 'png'
                    image_cache_path = os.path.join(cache_path, f"image_{len(blocks)}.{image_ext}")
                    try:
                        with open(image_cache_path, 'wb') as f:
                            f.write(image_data)
                    except Exception as e:
                        print(f"[WordParser] 保存图片缓存失败: {e}")
                        image_cache_path = None

                    block = DataBlock(
                        block_id=self._generate_block_id(file_path, len(blocks)),
                        modality=ModalityType.IMAGE,
                        addr=image_cache_path,
                        file_path=file_path,
                        metadata={
                            'source': 'python-docx',
                            'image_ref': rel.target_ref
                        }
                    )
                    blocks.append(block)
                except Exception:
                    pass

        return blocks

    def _parse_doc(self, file_path: str) -> List[DataBlock]:
        """解析doc文件（需要LibreOffice转换）"""
        try:
            import subprocess
            import tempfile

            temp_dir = tempfile.gettempdir()
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            docx_path = os.path.join(temp_dir, f"{base_name}.docx")

            result = subprocess.run(
                ['soffice', '--headless', '--convert-to', 'docx',
                 '--outdir', temp_dir, file_path],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and os.path.exists(docx_path):
                blocks = self._parse_docx(docx_path)
                os.remove(docx_path)
                return blocks
            else:
                raise RuntimeError(
                    "Failed to convert .doc file. Please install LibreOffice "
                    "or convert the file to .docx format manually."
                )
        except Exception as e:
            raise RuntimeError(
                f"Error parsing .doc file: {str(e)}. "
                "Consider converting to .docx format."
            )

    def _table_to_text(self, table_data: List[List[str]]) -> str:
        """将表格转换为文本"""
        rows = []
        for row in table_data:
            row_text = ' | '.join(str(cell) if cell else '' for cell in row)
            rows.append(row_text)
        return '\n'.join(rows)
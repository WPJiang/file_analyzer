import os
import hashlib
from typing import List
from .base_parser import BaseParser, DataBlock, ModalityType


class PPTParser(BaseParser):
    """PPT文件解析器

    将PPT文件解析为数据块，保存到cache目录下。
    """
    def __init__(self, cache_dir: str = "cache/data_blocks"):
        super().__init__()
        self.supported_extensions = ['pptx', 'ppt']
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
        """解析PPT文件"""
        if not self.can_parse(file_path):
            raise ValueError(f"Unsupported file format: {file_path}")

        ext = file_path.lower().split('.')[-1]

        if ext == 'ppt':
            return self._parse_ppt(file_path)
        else:
            return self._parse_pptx(file_path)

    def _parse_pptx(self, file_path: str) -> List[DataBlock]:
        """解析pptx文件"""
        try:
            from pptx import Presentation
        except ImportError:
            raise ImportError(
                "python-pptx is required for PowerPoint file parsing. "
                "Install it with: pip install python-pptx"
            )

        blocks = []
        prs = Presentation(file_path)

        # 获取缓存目录
        cache_path = self._get_cache_path(file_path)

        for slide_num, slide in enumerate(prs.slides, 1):
            slide_texts = []

            for shape in slide.shapes:
                # 解析文本
                if hasattr(shape, "text") and shape.text.strip():
                    slide_texts.append(shape.text)

                    # 保存文本到缓存
                    text_cache_path = os.path.join(cache_path, f"text_{slide_num}_{len(blocks)}.txt")
                    try:
                        with open(text_cache_path, 'w', encoding='utf-8') as f:
                            f.write(shape.text)
                    except Exception as e:
                        print(f"[PPTParser] 保存文本缓存失败: {e}")
                        text_cache_path = None

                    block = DataBlock(
                        block_id=self._generate_block_id(file_path, len(blocks)),
                        modality=ModalityType.TEXT,
                        addr=text_cache_path,
                        file_path=file_path,
                        page_number=slide_num,
                        metadata={
                            'source': 'python-pptx',
                            'slide_number': slide_num,
                            'shape_type': str(shape.shape_type),
                            'shape_name': shape.name
                        }
                    )
                    blocks.append(block)

                # 解析表格
                if shape.has_table:
                    table = shape.table
                    table_data = []
                    for row in table.rows:
                        row_data = [cell.text for cell in row.cells]
                        table_data.append(row_data)

                    table_text = self._table_to_text(table_data)

                    # 保存表格到缓存
                    table_cache_path = os.path.join(cache_path, f"table_{slide_num}_{len(blocks)}.txt")
                    try:
                        with open(table_cache_path, 'w', encoding='utf-8') as f:
                            f.write(table_text)
                    except Exception as e:
                        print(f"[PPTParser] 保存表格缓存失败: {e}")
                        table_cache_path = None

                    block = DataBlock(
                        block_id=self._generate_block_id(file_path, len(blocks)),
                        modality=ModalityType.TABLE,
                        addr=table_cache_path,
                        file_path=file_path,
                        page_number=slide_num,
                        metadata={
                            'source': 'python-pptx',
                            'slide_number': slide_num,
                            'rows': len(table_data),
                            'cols': len(table_data[0]) if table_data else 0
                        }
                    )
                    blocks.append(block)

                # 解析图片
                if hasattr(shape, "image"):
                    try:
                        image = shape.image
                        image_bytes = image.blob

                        # 保存图片到缓存
                        image_ext = image.ext if hasattr(image, 'ext') else 'png'
                        image_cache_path = os.path.join(cache_path, f"image_{slide_num}_{len(blocks)}.{image_ext}")
                        try:
                            with open(image_cache_path, 'wb') as f:
                                f.write(image_bytes)
                        except Exception as e:
                            print(f"[PPTParser] 保存图片缓存失败: {e}")
                            image_cache_path = None

                        block = DataBlock(
                            block_id=self._generate_block_id(file_path, len(blocks)),
                            modality=ModalityType.IMAGE,
                            addr=image_cache_path,
                            file_path=file_path,
                            page_number=slide_num,
                            metadata={
                                'source': 'python-pptx',
                                'slide_number': slide_num,
                                'image_ext': image_ext,
                                'content_type': image.content_type if hasattr(image, 'content_type') else None
                            }
                        )
                        blocks.append(block)
                    except Exception:
                        pass

            # 创建幻灯片摘要块
            if slide_texts:
                slide_summary = '\n'.join(slide_texts)

                # 保存幻灯片摘要到缓存
                summary_cache_path = os.path.join(cache_path, f"slide_summary_{slide_num}.txt")
                try:
                    with open(summary_cache_path, 'w', encoding='utf-8') as f:
                        f.write(slide_summary)
                except Exception as e:
                    print(f"[PPTParser] 保存幻灯片摘要缓存失败: {e}")
                    summary_cache_path = None

                block = DataBlock(
                    block_id=self._generate_block_id(file_path, f"slide_{slide_num}"),
                    modality=ModalityType.TEXT,
                    addr=summary_cache_path,
                    file_path=file_path,
                    page_number=slide_num,
                    metadata={
                        'source': 'python-pptx',
                        'type': 'slide_summary',
                        'slide_number': slide_num
                    }
                )
                blocks.append(block)

        return blocks

    def _parse_ppt(self, file_path: str) -> List[DataBlock]:
        """解析ppt文件（需要LibreOffice转换）"""
        try:
            import subprocess
            import tempfile

            temp_dir = tempfile.gettempdir()
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            pptx_path = os.path.join(temp_dir, f"{base_name}.pptx")

            result = subprocess.run(
                ['soffice', '--headless', '--convert-to', 'pptx',
                 '--outdir', temp_dir, file_path],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and os.path.exists(pptx_path):
                blocks = self._parse_pptx(pptx_path)
                os.remove(pptx_path)
                return blocks
            else:
                raise RuntimeError(
                    "Failed to convert .ppt file. Please install LibreOffice "
                    "or convert the file to .pptx format manually."
                )
        except Exception as e:
            raise RuntimeError(
                f"Error parsing .ppt file: {str(e)}. "
                "Consider converting to .pptx format."
            )

    def _table_to_text(self, table_data: List[List[str]]) -> str:
        """将表格转换为文本"""
        rows = []
        for row in table_data:
            row_text = ' | '.join(str(cell) if cell else '' for cell in row)
            rows.append(row_text)
        return '\n'.join(rows)
from typing import List, Tuple

# 型タイプ
RGB = Tuple[int, int, int]
"""RGB Type (Red, Blue, Green)"""

InputDataSize = Tuple[int, int]
"""画像データサイズType(width, height)"""

SubInputDataList = List[Tuple[str, str]]
"""Tuple(Jsonファイルのパス, 塗りつぶしアノテーションが格納されたディレクトリのパス)のList"""

"""
アノテーション検証のサンプル関数

このファイルは、annofabcli annotation_zip validateコマンドで使用する
バリデーション関数のサンプルです。

バリデーション関数は以下のルールに従って定義してください：
1. 関数名は 'validate_' から始める
2. 引数は detail: dict[str, Any] のみ
3. 戻り値は bool (True: 正常, False: 異常)
"""

from typing import Any


def validate_bounding_box_size(detail: dict[str, Any]) -> bool:
    """
    矩形アノテーションのサイズが適切かチェックする。
    
    Args:
        detail: アノテーション詳細辞書
        
    Returns:
        True: 正常, False: 異常
    """
    # 矩形アノテーションのみをチェック
    if detail.get("data", {}).get("_type") != "BoundingBox":
        return True
    
    data = detail.get("data", {})
    left_top = data.get("left_top", {})
    right_bottom = data.get("right_bottom", {})
    
    if not left_top or not right_bottom:
        return False
    
    # 矩形のサイズを計算
    width = right_bottom.get("x", 0) - left_top.get("x", 0)
    height = right_bottom.get("y", 0) - left_top.get("y", 0)
    
    # 最小サイズのチェック（例：10x10ピクセル以上）
    min_size = 10
    if width < min_size or height < min_size:
        return False
    
    # 最大サイズのチェック（例：2000x2000ピクセル以下）
    max_size = 2000
    if width > max_size or height > max_size:
        return False
    
    return True


def validate_required_attributes(detail: dict[str, Any]) -> bool:
    """
    必須の属性が設定されているかチェックする。
    
    Args:
        detail: アノテーション詳細辞書
        
    Returns:
        True: 正常, False: 異常
    """
    attributes = detail.get("attributes", {})
    
    # 特定のラベルには必須属性があることをチェック
    label = detail.get("label")
    if label == "person":
        # personラベルには"gender"属性が必須
        if "gender" not in attributes:
            return False
        if not attributes["gender"]:  # 空文字列や None もNG
            return False
    
    elif label == "vehicle":
        # vehicleラベルには"type"属性が必須
        if "type" not in attributes:
            return False
        if not attributes["type"]:
            return False
    
    return True


def validate_coordinate_range(detail: dict[str, Any]) -> bool:
    """
    座標値が適切な範囲内にあるかチェックする。
    
    Args:
        detail: アノテーション詳細辞書
        
    Returns:
        True: 正常, False: 異常
    """
    data = detail.get("data", {})
    data_type = data.get("_type")
    
    # 座標を含むアノテーションタイプのみチェック
    if data_type in ["BoundingBox", "Points", "Polyline", "Polygon"]:
        # 座標の最小値・最大値（例：0-4000ピクセルの範囲）
        min_coord = 0
        max_coord = 4000
        
        if data_type == "BoundingBox":
            left_top = data.get("left_top", {})
            right_bottom = data.get("right_bottom", {})
            
            coords = [
                left_top.get("x", 0), left_top.get("y", 0),
                right_bottom.get("x", 0), right_bottom.get("y", 0)
            ]
            
        elif data_type in ["Points", "Polyline", "Polygon"]:
            points = data.get("points", [])
            coords = []
            for point in points:
                coords.extend([point.get("x", 0), point.get("y", 0)])
        else:
            return True
        
        # すべての座標が範囲内かチェック
        for coord in coords:
            if coord < min_coord or coord > max_coord:
                return False
    
    return True


def validate_annotation_count(detail: dict[str, Any]) -> bool:
    """
    特定のラベルの数が適切かチェックする。
    ※ このサンプルでは個別のアノテーションをチェックするため、
    実際にはタスク単位での集計が必要ですが、簡単な例として示します。
    
    Args:
        detail: アノテーション詳細辞書
        
    Returns:
        True: 正常, False: 異常
    """
    # この関数は個別アノテーションでは意味がないため、常にTrueを返す
    # 実際のアノテーション数チェックは別途タスク単位で実装する必要があります
    return True


def validate_label_name_format(detail: dict[str, Any]) -> bool:
    """
    ラベル名の形式が正しいかチェックする。
    
    Args:
        detail: アノテーション詳細辞書
        
    Returns:
        True: 正常, False: 異常
    """
    label = detail.get("label", "")
    
    # ラベル名が空でないかチェック
    if not label:
        return False
    
    # ラベル名に許可された文字のみ含まれているかチェック
    # 例：英数字、アンダースコア、ハイフンのみ許可
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', label):
        return False
    
    # 予約語をチェック
    reserved_words = ["null", "undefined", "none"]
    if label.lower() in reserved_words:
        return False
    
    return True
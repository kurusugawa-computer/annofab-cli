import annofabapi
from annofabapi.plugin import EditorPluginId, ExtendSpecsPluginId


class Project:
    """
    Annofabプロジェクトに対応するクラス
    """

    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        project, _ = service.api.get_project(project_id)
        self.project = project

    def is_3d_annotation_editor_available(self) -> bool:
        """標準の3次元アノテーションエディタを利用できるか"""
        configuration = self.project["configuration"]
        return configuration["plugin_id"] == EditorPluginId.THREE_DIMENSION

    def is_3d_annotation_type_available(self) -> bool:
        """3次元のアノテーション種類を利用できるか"""
        configuration = self.project["configuration"]
        return configuration["extended_specs_plugin_id"] == ExtendSpecsPluginId.THREE_DIMENSION

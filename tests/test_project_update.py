from pathlib import Path

from annofabcli.project.update_project import (
    create_updated_project_list_from_csv,
    create_updated_project_list_from_dict,
)

test_dir = Path("tests/data/project/update")


class TestCreateUpdatedProjectListFromDict:
    def test_create_updated_project_list_from_dict(self):
        """辞書のリストからUpdatedProjectのリストを作成するテスト"""
        project_dict_list = [
            {"project_id": "prj1", "title": "new_title1"},
            {"project_id": "prj2", "overview": "new_overview2"},
            {"project_id": "prj3", "title": "new_title3", "overview": "new_overview3"},
        ]

        updated_project_list = create_updated_project_list_from_dict(project_dict_list)

        assert len(updated_project_list) == 3

        # 1つ目のプロジェクト
        assert updated_project_list[0].project_id == "prj1"
        assert updated_project_list[0].title == "new_title1"
        assert updated_project_list[0].overview is None

        # 2つ目のプロジェクト
        assert updated_project_list[1].project_id == "prj2"
        assert updated_project_list[1].title is None
        assert updated_project_list[1].overview == "new_overview2"

        # 3つ目のプロジェクト
        assert updated_project_list[2].project_id == "prj3"
        assert updated_project_list[2].title == "new_title3"
        assert updated_project_list[2].overview == "new_overview3"


class TestCreateUpdatedProjectListFromCsv:
    def test_create_updated_project_list_from_csv(self):
        """CSVファイルからUpdatedProjectのリストを作成するテスト"""
        # テスト用のCSVファイルを作成
        updated_project_list = create_updated_project_list_from_csv(test_dir / "test_projects.csv")

        assert len(updated_project_list) == 3

        # 1つ目のプロジェクト
        assert updated_project_list[0].project_id == "prj1"
        assert updated_project_list[0].title == "new_title1"
        assert updated_project_list[0].overview == "new_overview1"

        # 2つ目のプロジェクト（titleが空文字列）
        assert updated_project_list[1].project_id == "prj2"
        # pandas読み込み時に空文字列はNaNになる場合があるため、None または空文字列を許可
        assert updated_project_list[1].title is None
        assert updated_project_list[1].overview == "new_overview2"

        # 3つ目のプロジェクト（overviewが空文字列）
        assert updated_project_list[2].project_id == "prj3"
        assert updated_project_list[2].title == "new_title3"
        # pandas読み込み時に空文字列はNaNになる場合があるため、None または空文字列を許可
        assert updated_project_list[2].overview is None

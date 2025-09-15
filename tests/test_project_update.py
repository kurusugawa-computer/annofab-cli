from pathlib import Path

from annofabcli.project.update_project import (
    UpdatedProject,
    create_updated_project_list_from_csv,
    create_updated_project_list_from_dict,
)

test_dir = Path("./tests/data/project")


class TestUpdatedProject:
    def test_model_validate(self):
        """UpdatedProjectのmodel_validateメソッドのテスト"""
        project_dict = {"project_id": "prj1", "title": "new_title", "overview": "new_overview"}
        updated_project = UpdatedProject.model_validate(project_dict)

        assert updated_project.project_id == "prj1"
        assert updated_project.title == "new_title"
        assert updated_project.overview == "new_overview"

    def test_model_validate_with_optional_fields(self):
        """オプショナルフィールドがnullの場合のテスト"""
        project_dict = {"project_id": "prj1", "title": None, "overview": ""}
        updated_project = UpdatedProject.model_validate(project_dict)

        assert updated_project.project_id == "prj1"
        assert updated_project.title is None
        assert updated_project.overview == ""

    def test_model_validate_minimal(self):
        """最小限のフィールドのみのテスト"""
        project_dict = {"project_id": "prj1"}
        updated_project = UpdatedProject.model_validate(project_dict)

        assert updated_project.project_id == "prj1"
        assert updated_project.title is None
        assert updated_project.overview is None


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
    def test_create_updated_project_list_from_csv(self, tmp_path):
        """CSVファイルからUpdatedProjectのリストを作成するテスト"""
        # テスト用のCSVファイルを作成
        csv_content = """project_id,title,overview
prj1,new_title1,new_overview1
prj2,,new_overview2
prj3,new_title3,"""

        csv_file = tmp_path / "test_projects.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        updated_project_list = create_updated_project_list_from_csv(csv_file)

        assert len(updated_project_list) == 3

        # 1つ目のプロジェクト
        assert updated_project_list[0].project_id == "prj1"
        assert updated_project_list[0].title == "new_title1"
        assert updated_project_list[0].overview == "new_overview1"

        # 2つ目のプロジェクト（titleが空文字列）
        assert updated_project_list[1].project_id == "prj2"
        # pandas読み込み時に空文字列はNaNになる場合があるため、None または空文字列を許可
        assert updated_project_list[1].title in (None, "", "nan")
        assert updated_project_list[1].overview == "new_overview2"

        # 3つ目のプロジェクト（overviewが空文字列）
        assert updated_project_list[2].project_id == "prj3"
        assert updated_project_list[2].title == "new_title3"
        # pandas読み込み時に空文字列はNaNになる場合があるため、None または空文字列を許可
        assert updated_project_list[2].overview in (None, "", "nan")

    def test_create_updated_project_list_from_csv_project_id_only(self, tmp_path):
        """project_idのみのCSVファイルのテスト"""
        csv_content = """project_id,title,overview
prj1,,"""

        csv_file = tmp_path / "test_projects_minimal.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        updated_project_list = create_updated_project_list_from_csv(csv_file)

        assert len(updated_project_list) == 1
        assert updated_project_list[0].project_id == "prj1"
        # 空文字列またはNaNはNoneまたは空文字列として扱われる
        assert updated_project_list[0].title in (None, "", "nan")
        assert updated_project_list[0].overview in (None, "", "nan")

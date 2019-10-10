import os
from pathlib import Path

from annofabapi.models import ProjectMemberRole

from annofabcli.project_member.put_project_members import Member, PutProjectMembers
from annofabcli.project_member.change_project_members import ChangeProjectMembers

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path('./tests/data')
out_dir = Path('./tests/out')

class TestPutProjectMembers:
    def test_get_members_from_csv(self):
        csv_path = test_dir / "project_members.csv"
        actual_members = PutProjectMembers.get_members_from_csv(csv_path)
        expected_members = [
            Member("user1", ProjectMemberRole.OWNER),
            Member("user2", ProjectMemberRole.ACCEPTER),
            Member("user3", ProjectMemberRole.WORKER),
            Member("user4", ProjectMemberRole.TRAINING_DATA_USER),
        ]
        assert actual_members == expected_members

class TestChangeProjectMembers:
    def test_validate_member_info(self):
        assert ChangeProjectMembers.validate_member_info(
            {"sampling_inspection_rate": 10, "sampling_acceptance_rate": 20, "foo": "bar"}) == True

        assert ChangeProjectMembers.validate_member_info(
            {"sampling_inspection_rate": 10}) == True

        assert ChangeProjectMembers.validate_member_info({"sampling_acceptance_rate": 20}) == True

        assert ChangeProjectMembers.validate_member_info({}) == False

        assert ChangeProjectMembers.validate_member_info({"foo":"bar"}) == False

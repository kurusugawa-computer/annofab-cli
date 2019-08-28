import os
from pathlib import Path

from annofabapi.models import ProjectMemberRole

from annofabcli.project_member.put_project_members import Member, PutProjectMembers

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path('./tests/data')
out_dir = Path('./tests/out')


def test_get_members_from_csv():
    csv_path = test_dir / "project_members.csv"
    actual_members = PutProjectMembers.get_members_from_csv(csv_path)
    expected_members = [
        Member("user1", ProjectMemberRole.OWNER),
        Member("user2", ProjectMemberRole.ACCEPTER),
        Member("user3", ProjectMemberRole.WORKER),
        Member("user4", ProjectMemberRole.TRAINING_DATA_USER),
    ]
    assert actual_members == expected_members

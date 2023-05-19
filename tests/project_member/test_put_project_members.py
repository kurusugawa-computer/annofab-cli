from pathlib import Path

from annofabapi.models import ProjectMemberRole

from annofabcli.project_member.put_project_members import Member, PutProjectMembers

data_dir = Path("./tests/data/project_member")


class TestPutProjectMembers:
    def test_get_members_from_csv(self):
        csv_path = data_dir / "project_members.csv"
        actual_members = PutProjectMembers.get_members_from_csv(csv_path)
        expected_members = [
            Member("user1", ProjectMemberRole.OWNER, sampling_inspection_rate=None, sampling_acceptance_rate=None),
            Member("user2", ProjectMemberRole.ACCEPTER, sampling_inspection_rate=10, sampling_acceptance_rate=20),
            Member("user3", ProjectMemberRole.WORKER, sampling_inspection_rate=None, sampling_acceptance_rate=20),
            Member(
                "user4",
                ProjectMemberRole.TRAINING_DATA_USER,
                sampling_inspection_rate=10,
                sampling_acceptance_rate=None,
            ),
        ]
        assert actual_members == expected_members

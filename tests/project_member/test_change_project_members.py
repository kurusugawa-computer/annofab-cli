from annofabcli.project_member.change_project_members import ChangeProjectMembers


class TestChangeProjectMembers:
    def test_validate_member_info(self):
        assert ChangeProjectMembers.validate_member_info({"sampling_inspection_rate": 10, "sampling_acceptance_rate": 20, "foo": "bar"}) is True

        assert ChangeProjectMembers.validate_member_info({"sampling_inspection_rate": 10}) is True

        assert ChangeProjectMembers.validate_member_info({"sampling_acceptance_rate": 20}) is True

        assert ChangeProjectMembers.validate_member_info({}) is False

        assert ChangeProjectMembers.validate_member_info({"foo": "bar"}) is False

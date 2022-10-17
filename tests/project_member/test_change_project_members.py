from annofabcli.project_member.change_project_members import ChangeProjectMembers


class TestChangeProjectMembers:
    def test_validate_member_info(self):
        assert (
            ChangeProjectMembers.validate_member_info(
                {"sampling_inspection_rate": 10, "sampling_acceptance_rate": 20, "foo": "bar"}
            )
            == True
        )

        assert ChangeProjectMembers.validate_member_info({"sampling_inspection_rate": 10}) == True

        assert ChangeProjectMembers.validate_member_info({"sampling_acceptance_rate": 20}) == True

        assert ChangeProjectMembers.validate_member_info({}) == False

        assert ChangeProjectMembers.validate_member_info({"foo": "bar"}) == False

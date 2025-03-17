from annofabcli.supplementary.put_supplementary_data import convert_supplementary_data_name_to_supplementary_data_id


def test__convert_supplementary_data_name_to_supplementary_data_id():
    assert convert_supplementary_data_name_to_supplementary_data_id("a/b/c.png") == "a__b__c.png"
    assert convert_supplementary_data_name_to_supplementary_data_id("s3://foo.png") == "s3______foo.png"
    assert convert_supplementary_data_name_to_supplementary_data_id("あ.png") == "__.png"

=================================
input_data delete_metadata_key
=================================

Description
=================================
入力データのメタデータのキーを削除します。


Examples
=================================


``--metadata_key`` に削除したいメタデータのキーを指定します。


.. code-block::

    $ annofabcli input_data delete_metadata_key --project_id prj1 --input_data_id input1 input2 \
     --metadata_key foo bar



.. warning::

    入力データのメタデータを更新すると、入力データの ``updated_datetime`` （更新日時）が更新されます。
    入力データの更新日時は、入力データの登録以外でも更新されることに注意してください。
    




Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.delete_metadata_key_of_input_data.add_parser
   :prog: annofabcli input_data delete_metadata_key
   :nosubcommands:
   :nodefaultconst:

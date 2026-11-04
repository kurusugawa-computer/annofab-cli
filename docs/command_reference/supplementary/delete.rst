=================================
supplementary delete
=================================

Description
=================================
指定した入力データに紐づくすべての補助情報を削除します。
入力データごとに削除を確認します。


個別の補助情報をCSVまたはJSONで指定する場合は、:doc:`delete_per_supplementary_data` を使用してください。
従来の ``--csv`` と ``--json`` は、そのコマンドに移動しました。

Examples
=================================


基本的な使い方
--------------------------


入力データに紐づく全ての補助情報を削除する
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
``--input_data_id`` に入力データのinput_data_idを指定すると、入力データに紐づく全ての補助情報を削除します。


.. code-block::

    $ annofabcli supplementary delete --project_id prj1 --input_data_id input1 input2



Usage Details
=================================

.. argparse::
   :ref: annofabcli.supplementary.delete_supplementary_data.create_parser
   :prog: annofabcli supplementary delete
   :nosubcommands:
   :nodefaultconst:

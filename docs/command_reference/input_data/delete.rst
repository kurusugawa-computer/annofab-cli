=================================
input_data delete
=================================

Description
=================================
入力データを削除します。


Examples
=================================


基本的な使い方
--------------------------

``--input_data_id`` に削除対象入力データのinput_data_idを指定してください。


.. code-block::
    :caption: input_data_id.txt

    input1
    input2
    ...

以下のコマンドは、``input_data_id.txt`` に記載されているinput_data_idに一致する入力データを削除します。

.. code-block::

    $ annofabcli input_data delete --project_id prj1 --input_data_id file://input_data_id.txt

デフォルトでは、タスクに使われている入力データを削除しません。
タスクに使われている入力データを削除するには、``--force`` を指定してください。


.. code-block::

    $ annofabcli input_data delete --project_id prj1 --input_data_id file://input_data_id.txt \
    --force

.. warning::

    タスクに使わている入力データを削除すると、削除対象の入力データに付与されたアノテーションを、Annofabのアノテーションエディタ画面で確認することができません。


入力データに紐づく補助情報の削除
----------------------------------------------------

``--delete_supplementary`` を指定すると、入力データに紐づく補助情報も削除します。

.. code-block::

    $ annofabcli input_data delete --project_id prj1 --input_data_id file://input_data_id.txt \
     --delete_supplementary

Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.delete_input_data.add_parser
   :prog: annofabcli input_data delete
   :nosubcommands:
   :nodefaultconst:


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

以下のコマンドは、``input_data_id.txt`` に記載されているinput_data_idに一致する入力データを削除します。

.. code-block::

    $ annofabcli input_data delete --project_id prj1 --input_data_id file://input_data_id.txt

デフォルトでは、タスクに使われている入力データを削除しません。
タスクに使われている入力データを削除するには、``--force`` を指定してください。


.. code-block::

    $ annofabcli input_data delete --project_id prj1 --input_data_id file://input_data_id.txt \
    --force

.. warning::

    タスクに使わている入力データを削除すると、削除対象の入力データに付与されたアノテーションを、AnnoFabのアノテーションエディタ画面で確認することができません。

=================================
input_data update_metadata
=================================

Description
=================================
入力データのメタデータを更新します。


Examples
=================================



基本的な使い方
--------------------------------------

``--input_data_id`` にメタデータを付与する入力データのinput_data_idを指定してください。

.. code-block::
    :caption: input_data_id.txt

    input1
    input2
    ...


``--metadata`` に入力データに設定するメタデータをJSON形式で指定してください。
メタデータの値は文字列のみ指定できます。


.. code-block::

    $ annofabcli input_data update_metadata --project_id prj1 \
    --input_data_id file://input_data_id.txt \
    --metadata '{"category":"202010"}'


デフォルトでは ``--metadata`` に指定したキーのみ更新されます。メタデータ自体を上書きする場合は ``--overwrite`` を指定してください。


.. code-block::

    $ annofabcli input_data update_metadata --project_id prj1 --input_data_id input1 \
     --metadata '{"category":"202010"}'

    $ annofabcli input_data list --project_id prj1 --input_data_id input1 \
     --format json --query "[0].metadata"
    {"category": "202010"}

    # メタデータの一部のキーのみ更新する
    $ annofabcli input_data update_metadata --project_id prj1 --input_data_id input1 \
     --metadata '{"country":"Japan"}'
    $ annofabcli input_data list --project_id prj1 --input_data_id input1 \
     --format json --query "[0].metadata"
    {"category": "202010", "country":"Japan"}

    # メタデータ自体を上書きする
    $ annofabcli input_data update_metadata --project_id prj1 --input_data_id input1 \
     --metadata '{"weather":"sunny"}' --overwrite
    $ annofabcli input_data list --project_id prj1 --input_data_id input1 \
     --format json --query "[0].metadata"
    {"weather":"sunny"}




並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli input_data update_metadata --project_id prj1 \
     --input_data_id file://input_data_id.txt \
     --metadata '{"category":"202010"}' --parallelism 4 --yes


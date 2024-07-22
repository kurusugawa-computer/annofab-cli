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





.. note::

    入力データのメタデータは ``input_data list`` コマンドで確認できます。
    ``input_data list`` の出力結果は情報量が多いので、以下のようにjqコマンドを使って情報を絞り込むと、見やすくなります。
    
    .. code-block::
        
        $ annofabcli input_data list --project_id prj1 --input_data_id input1 --format json |
            jq '[.[] | {input_data,metadata}]'
        [
            {
                "input_data_id": "input1",
                "metadata": {
                    "category": "202010"
                }
            }
        ]  



.. code-block::

    $ annofabcli input_data update_metadata --project_id prj1 --input_data_id input1 \
     --metadata '{"category":"202010"}'

    $ annofabcli input_data list --project_id prj1 --input_data_id input1 \
     --format json | jq '.[].metadata'
    {
        "category": "202010"
    }

    # メタデータの一部のキーのみ更新する
    $ annofabcli input_data update_metadata --project_id prj1 --input_data_id input1 \
     --metadata '{"country":"Japan"}'
    
    $ annofabcli input_data list --project_id prj1 --input_data_id input1 \
     --format json | jq '.[].metadata'
    {
        "category": "202010",
        "country":"Japan"
    }

    # メタデータ自体を上書きする
    $ annofabcli input_data update_metadata --project_id prj1 --input_data_id input1 \
     --metadata '{"weather":"sunny"}' --overwrite
    
    $ annofabcli input_data list --project_id prj1 --input_data_id input1 \
     --format json | jq '.[].metadata'
    {
        "weather":"sunny"
    }




.. warning::

    入力データのメタデータを更新すると、入力データの ``updated_datetime`` （更新日時）が更新されます。
    入力データの更新日時は、入力データの登録以外でも更新されることに注意してください。



入力データごとにメタデータを指定する
--------------------------------------

``--metadata_by_input_data_id`` を指定すれば、入力データごとにメタデータを指定できます。


.. code-block:: json
    :caption: all_metadata.json
    
    {
      "input_data1": {"country":"japan"},
      "input_data2": {"country":"us"}
    }
    
    
.. code-block::

    $ annofabcli input_data update_metadata --project_id prj1 \
     --metadata_by_input_data_id file://all_metadata.json




並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli input_data update_metadata --project_id prj1 \
     --input_data_id file://input_data_id.txt \
     --metadata '{"category":"202010"}' --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.update_metadata_of_input_data.add_parser
   :prog: annofabcli input_data update_metadata
   :nosubcommands:
   :nodefaultconst:

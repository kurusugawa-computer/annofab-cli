=================================
input_data update
=================================

Description
=================================
入力データの名前または入力データのパスを更新します。


Examples
=================================




CSVファイルを指定する場合
--------------------------------------
``--csv`` に、更新対象の入力データ情報が記載されたCSVファイルのパスを指定してください。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行あり

.. csv-table::
   :header: 列名,必須,備考

    input_data_id,Yes,更新対象の入力データID
    input_data_name,No,変更後の入力データ名。更新しない場合は空欄
    input_data_path,No,変更後の入力データパス。更新しない場合は空欄


以下はCSVファイルのサンプルです。

.. code-block::
    :caption: input_data.csv

    input_data_id,input_data_name,input_data_path
    id1,new_name1,
    id2,,s3://bucket/new_image.jpg
    id3,new_name3,https://example.com/new_image.jpg


.. warning::

    プライベートストレージが利用可能な組織配下のプロジェクトでしか、 ``input_data_path`` に ``https`` または ``s3`` スキームを利用できません。
    プライベートストレージを利用するには、Annofabサポート窓口への問い合わせが必要です。
    詳細は https://annofab.readme.io/docs/external-storage を参照してください。



.. code-block::

    $ annofabcli input_data update --project_id prj1 --csv input_data.csv




JSON文字列を指定する場合
--------------------------------------
``--json`` に、更新対象の入力データ情報をJSON文字列で指定してください。

以下は、JSONのサンプルです。

.. code-block::
    :caption: input_data.json

    [
        {
            "input_data_id": "id1",
            "input_data_name": "new_name1"
        },
        {
            "input_data_id": "id2",
            "input_data_path": "s3://bucket/new_image.jpg"
        },
        {
            "input_data_id": "id3",
            "input_data_name": "new_name3",
            "input_data_path": "https://example.com/new_image.jpg"
        }
    ]

JSONのキーは、 ``--csv`` に指定するCSVファイルの列に対応します。
更新しないプロパティは、キーを記載しないか値をnullにしてください。

``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli input_data update --project_id prj1 --json file://input_data.json





Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.update_input_data.add_parser
   :prog: annofabcli input_data update
   :nosubcommands:
   :nodefaultconst:

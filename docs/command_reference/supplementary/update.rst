=================================
supplementary update
=================================

Description
=================================
補助情報の名前、パス、種類、表示順を更新します。


Examples
=================================


CSVファイルを指定する場合
--------------------------------------
``--csv`` に、更新対象の補助情報と更新後の値が記載されたCSVファイルのパスを指定してください。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行あり

.. csv-table::
   :header: 列名,必須,備考

    input_data_id,Yes,更新対象の補助情報が紐づく入力データID
    supplementary_data_id,Yes,更新対象の補助情報ID
    supplementary_data_name,No,変更後の補助情報名。更新しない場合は空欄
    supplementary_data_path,No,変更後の補助情報パス。更新しない場合は空欄。先頭が ``file://`` の場合、ローカルのファイルを補助情報に使用します。
    supplementary_data_type,No,変更後の補助情報の種類。更新しない場合は空欄
    supplementary_data_number,No,変更後の補助情報の表示順。更新しない場合は空欄


以下はCSVファイルのサンプルです。

.. code-block::
    :caption: supplementary_data.csv

    input_data_id,supplementary_data_id,supplementary_data_name,supplementary_data_path,supplementary_data_type,supplementary_data_number
    input1,supplementary1,new_name1,,,
    input1,supplementary2,,s3://bucket/new_image.jpg,,
    input2,supplementary3,new_name3,https://example.com/new_image.jpg,image,2
    input2,supplementary4,,file://new_image.jpg,,


.. warning::

    プライベートストレージが利用可能な組織配下のプロジェクトでしか、 ``supplementary_data_path`` に ``https`` または ``s3`` スキームを利用できません。
    プライベートストレージを利用するには、Annofabサポート窓口への問い合わせが必要です。
    詳細は https://annofab.readme.io/docs/external-storage を参照してください。

``supplementary_data_path`` の先頭が ``file://`` の場合、指定したローカルファイルをアップロードし、補助情報のパスをアップロード後のパスに更新します。


.. code-block::

    $ annofabcli supplementary update --project_id prj1 --csv supplementary_data.csv


JSON文字列を指定する場合
--------------------------------------
``--json`` に、更新対象の補助情報と更新後の値をJSON文字列で指定してください。

以下は、JSONのサンプルです。

.. code-block::
    :caption: supplementary_data.json

    [
        {
            "input_data_id": "input1",
            "supplementary_data_id": "supplementary1",
            "supplementary_data_name": "new_name1"
        },
        {
            "input_data_id": "input1",
            "supplementary_data_id": "supplementary2",
            "supplementary_data_path": "s3://bucket/new_image.jpg"
        },
        {
            "input_data_id": "input2",
            "supplementary_data_id": "supplementary3",
            "supplementary_data_name": "new_name3",
            "supplementary_data_path": "https://example.com/new_image.jpg",
            "supplementary_data_type": "image",
            "supplementary_data_number": 2
        },
        {
            "input_data_id": "input2",
            "supplementary_data_id": "supplementary4",
            "supplementary_data_path": "file://new_image.jpg"
        }
    ]

JSONのキーは、 ``--csv`` に指定するCSVファイルの列に対応します。
更新しないプロパティは、キーを記載しないか値をnullにしてください。

``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli supplementary update --project_id prj1 --json file://supplementary_data.json


Usage Details
=================================

.. argparse::
   :ref: annofabcli.supplementary.update_supplementary_data.add_parser
   :prog: annofabcli supplementary update
   :nosubcommands:
   :nodefaultconst:

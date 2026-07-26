=======================================================
annotation_specs list_annotation_import_info
=======================================================

Description
=================================
アノテーションをimportする際に参照すべき情報（ラベル、属性、選択肢）のみを出力します。

``annotation import`` のJSONに指定するラベル名、属性名、選択肢名を確認するためのコマンドです。
日本語名、色情報、ID、キーバインドなど、``annotation import`` で直接参照しない情報は出力しません。


Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_specs list_annotation_import_info --project_id prj1 --format pretty_json

デフォルトでは最新のアノテーション仕様を出力します。過去のアノテーション仕様を出力する場合は、``--before`` または ``--history_id`` を指定してください。
history_idは、`annofabcli annotation_specs list_history <../annotation_specs/list_history.html>`_ コマンドで取得できます。

以下のコマンドは、最新より1つ前のアノテーション仕様を出力します。

.. code-block::

    $ annofabcli annotation_specs list_annotation_import_info --project_id prj1 --before 1


以下のコマンドは、history_idが"xxx"のアノテーション仕様を出力します。

.. code-block::

    $ annofabcli annotation_specs list_annotation_import_info --project_id prj1 --history_id xxx


アノテーション仕様JSONファイルを元に出力する
----------------------------------------------------

.. code-block::

    $ annofabcli annotation_specs list_annotation_import_info \
    --annotation_specs_json_file annotation_specs.json \
    --format pretty_json


出力結果
=================================

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs list_annotation_import_info --project_id prj1 --format pretty_json --output out.json


.. code-block::
    :caption: out.json

    [
        {
            "label_name_en": "car",
            "annotation_type": "bounding_box",
            "attributes": [
                {
                    "attribute_name_en": "occluded",
                    "attribute_type": "flag",
                    "choices": []
                },
                {
                    "attribute_name_en": "direction",
                    "attribute_type": "select",
                    "choices": [
                        {
                            "choice_name_en": "front"
                        },
                        {
                            "choice_name_en": "side"
                        }
                    ]
                }
            ]
        }
    ]


* ``label_name_en`` : ラベル名（英語）。``annotation import`` の ``label`` に指定する値です。
* ``annotation_type`` : アノテーションの種類。Web APIの `AnnotationType <https://annofab.com/docs/api/#tag/x-data-types/AnnotationType>`_ に対応しています。
* ``attributes`` : ラベルに指定できる属性情報の配列です。
* ``attribute_name_en`` : 属性名（英語）。``annotation import`` の ``attributes`` のキーに指定する値です。
* ``attribute_type`` : 属性の種類。WebAPIの ``AdditionalDataDefinitionType`` に対応しています。
* ``choices`` : 選択肢情報の配列です。属性の種類がラジオボタンまたはドロップダウン以外の場合は空配列です。
* ``choice_name_en`` : 選択肢名（英語）。属性の種類がラジオボタンまたはドロップダウンの場合に、``annotation import`` の ``attributes`` の値として指定する値です。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_annotation_import_info.add_parser
   :prog: annofabcli annotation_specs list_annotation_import_info
   :nosubcommands:
   :nodefaultconst:

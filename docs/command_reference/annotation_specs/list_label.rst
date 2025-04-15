==========================================
annotation_specs list_label
==========================================

Description
=================================
アノテーション仕様のラベル情報を出力します。




Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_specs list_label --project_id prj1

デフォルトでは最新のアノテーション仕様を出力します。過去のアノテーション仕様を出力する場合は、``--before`` または ``--history_id`` を指定してください。
history_idは、`annofabcli annotation_specs list_history <../annotation_specs/list_history.html>`_ コマンドで取得できます。

以下のコマンドは、最新より1つ前のアノテーション仕様を出力します。

.. code-block::

    $ annofabcli annotation_specs list_label --project_id prj1 --before 1


以下のコマンドは、history_idが"xxx"のアノテーション仕様を出力します。

.. code-block::

    $ annofabcli annotation_specs list_label --project_id prj1 --history_id xxx


出力結果
=================================



JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs list_label --project_id prj1  --format pretty_json --output out.json


.. code-block::
    :caption: out.json


    [
        {
            "label_id": "dc14bd37-c31e-4ca1-99f3-4025edae5bb9",
            "label_name_en": "car",
            "label_name_ja": "car",
            "label_name_vi": "car",
            "annotation_type": "bounding_box",
            "color": "#8100D8",
            "attribute_count": 5,
            "keybind": "Ctrl+Digit1"
        }
    ]



* ``label_id`` : ラベルID
* ``label_name_en`` : ラベル名（英語）
* ``label_name_ja`` : ラベル名（日本語）
* ``label_name_vi`` : ラベル名（ベトナム語）
* ``annotation_type`` : アノテーションの種類。Web APIの `AnnotationType <https://annofab.com/docs/api/#section/AnnotationType>`_ に対応しています。
* ``color`` : ラベルの色（HEX形式）。
* ``attribute_count`` : ラベルに紐づく属性の個数  
* ``keybind`` : キーボードショートカット




Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_annotation_specs_label.add_parser
   :prog: annofabcli annotation_specs list_label
   :nosubcommands:
   :nodefaultconst:



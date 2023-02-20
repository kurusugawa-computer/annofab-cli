==========================================
annotation_specs list_label_color
==========================================

Description
=================================
アノテーション仕様のラベル名(英語)と色(RGB)の対応関係を出力します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_specs list_label_color --project_id prj1 


出力結果
=================================




JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs list_label_color --project_id prj1  --format pretty_json --output out.json


.. code-block::
    :caption: out.json

    {
        "cat": [
            255,
            99,
            71
        ],
        "dog": [
            255,
            0,
            255
        ],
        ...
    }

Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_label_color.add_parser
   :prog: annofabcli annotation_specs list_label_color
   :nosubcommands:
   :nodefaultconst:


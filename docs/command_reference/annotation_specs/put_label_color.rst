==========================================
annotation_specs put_label_color
==========================================

Description
=================================
アノテーション仕様のラベルの色を変更します。


Examples
=================================

基本的な使い方
--------------------------

``--json`` には、変更したいラベルの色をJSON形式で指定してください。
keyがラベル英語名, valueがRGB値の配列です。


.. code-block::

    $ annofabcli annotation_specs put_label_color --project_id prj1 \
     --json '{"car":[255,0,0], "bike":[0,255,255]}'


.. note::

    ``--json`` に渡す値のフォーマットは、 `annofabcli annotation restore <../annotation/restore.html>`_  コマンドの出力結果と同じです。



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
   :ref: annofabcli.annotation_specs.put_label_color.add_parser
   :prog: annofabcli annotation_specs put_label_color
   :nosubcommands:
   :nodefaultconst:


==========================================
annotation_specs list_annotation_rule
==========================================

Description
=================================

プロジェクトのアノテーションルールを共有するために、ラベル、アノテーションの種類、属性、選択肢をMarkdown形式で出力します。
色、ショートカットキー、制約、ID、読み込み専用の設定は出力しません。


Examples
=================================

基本的な使い方
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs list_annotation_rule --project_id prj1
    # アノテーションルール

    ## 車
    - アノテーションの種類: `bounding_box`
    - 属性:
      - 向き: `select`
        - 選択肢:
          - 前
          - 横

名前は既定で日本語で出力します。英語名を出力する場合は ``--lang en`` を指定してください。

.. code-block::

    $ annofabcli annotation_specs list_annotation_rule --project_id prj1 --lang en
    # Annotation rules

    ## Car
    - Annotation type: `bounding_box`
    - Attributes:
      - Direction: `select`
        - Choices:
          - Front
          - Side

``--output`` を指定すると、Markdownファイルに出力できます。

.. code-block::

    $ annofabcli annotation_specs list_annotation_rule --project_id prj1 --output annotation_rule.md


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_annotation_rule.add_parser
   :prog: annofabcli annotation_specs list_annotation_rule
   :nosubcommands:
   :nodefaultconst:

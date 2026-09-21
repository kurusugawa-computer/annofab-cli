=================================================
annotation_specs describe_label_attributes
=================================================

Description
=================================

ラベルと、そのラベルで利用できる属性および選択肢の関係を、共有用のMarkdown形式で出力します。
ラベル色、ショートカットキー、ID、指定していない言語の名前、属性制約および定型指摘は出力しません。
読み込み専用の属性には、読み込み専用であることを記載します。


Examples
=================================

基本的な使い方
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs describe_label_attributes --project_id prj1
    # 「車」ラベル（矩形）

    - 「向き」属性（ドロップダウン）
      - 前
      - 横
    - 「遮蔽」属性（チェックボックス、読み込み専用）

名前は既定で日本語で出力します。英語名を出力する場合は ``--lang en`` を指定してください。

.. code-block::

    $ annofabcli annotation_specs describe_label_attributes --project_id prj1 --lang en
    # Label "Car" (Bounding box)

    - Attribute "Direction" (Dropdown)
      - Front
      - Side

``--output`` を指定すると、Markdownファイルに出力できます。

.. code-block::

    $ annofabcli annotation_specs describe_label_attributes --project_id prj1 --output label_attributes.md


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.describe_label_attributes.add_parser
   :prog: annofabcli annotation_specs describe_label_attributes
   :nosubcommands:
   :nodefaultconst:

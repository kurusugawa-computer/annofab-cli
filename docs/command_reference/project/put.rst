=================================
project put
=================================

Description
=================================
プロジェクトを作成します。

Examples
=================================

基本的な使い方
--------------------------

以下のコマンドは、組織orgに「foo」という画像プロジェクトを作成します。

.. code-block::

    $ annofabcli project put --organization org --title foo --input_data_type image


デフォルトでは、作成されるプロジェクトのproject_idはUUIDv4です。
``--project_id`` で作成されるプロジェクトのproject_idを指定することもできます。

.. code-block::

    $ annofabcli project put --organization org --title foo --input_data_type image \
     --project_id bar







Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.put_project.add_parser
   :prog: annofabcli project put
   :nosubcommands:
   :nodefaultconst:

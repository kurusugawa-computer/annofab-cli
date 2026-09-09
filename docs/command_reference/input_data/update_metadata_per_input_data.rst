==========================================
input_data update_metadata_per_input_data
==========================================

Description
=================================

入力データごとに指定したメタデータを更新します。


Examples
=================================

``--json`` には、キーを入力データID、値を設定するメタデータとしたJSONオブジェクトを指定します。
メタデータの値には文字列を指定できます。

.. code-block:: json
   :caption: all_metadata.json

   {
     "input_data1": {"country": "japan"},
     "input_data2": {"country": "us"}
   }

.. code-block::

   $ annofabcli input_data update_metadata_per_input_data --project_id prj1 \
     --json file://all_metadata.json

デフォルトでは、JSONに指定したキーのみ更新されます。メタデータ全体を上書きするには ``--overwrite`` を指定してください。既存メタデータの確認方法などは :doc:`update_metadata` を参照してください。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.update_metadata_per_input_data.add_parser
   :prog: annofabcli input_data update_metadata_per_input_data
   :nosubcommands:
   :nodefaultconst:

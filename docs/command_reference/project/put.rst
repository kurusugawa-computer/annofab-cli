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


デフォルトでは、作成したプロジェクトのproject_idのフォーマットはUUIDv4です。
``--project_id`` オプションで、作成するプロジェクトのproject_idを指定することもできます。

.. code-block::

    $ annofabcli project put --organization org --title foo --input_data_type image \
     --project_id bar


プロジェクトの設定情報を指定
----------------------------------------------------

``--configuration`` オプションで、プロジェクトの設定情報を指定できます。
以下のコマンドで作成したプロジェクトは、アノテーションエディタのバージョンがプレビュー版になります。

.. code-block::

    $ annofabcli project put --organization org --title foo --input_data_type image \
     --configuration '{"editor_version":"preview"}'


JSONの構造については、 `putProject <https://annofab.com/docs/api/#operation/putProject>`_ APIのリクエストボディを参照してください。



3次元プロジェクトの作成
----------------------------------------------------
3次元プロジェクトを作成するには、 ``--custom_project_type`` オプションも指定する必要があります。


.. code-block::

    $ annofabcli project put --organization org --title foo --input_data_type custom \
     --custom_project_type 3d

     





Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.put_project.add_parser
   :prog: annofabcli project put
   :nosubcommands:
   :nodefaultconst:

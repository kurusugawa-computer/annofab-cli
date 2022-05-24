=================================
filesystem write_annotation_image
=================================

Description
=================================
アノテーションzip、またはそれを展開したディレクトリから、Semantic Segmentation用のアノテーションの画像を生成します。

画像化対象のアノテーションは、アノテーションデータの ``_type`` が以下の場合です。

* ``BoundingBox`` （矩形）
* ``Points``  （ポリゴン or ポリライン）
* ``Segmentation`` （塗りつぶし）
* ``SegmentationV2`` （塗りつぶしv2）



Examples
=================================


基本的な使い方
--------------------------

``--annotation`` には、Annofabからダウンロードしたアノテーションzipか、アノテーションzipを展開したディレクトリを指定してください。
アノテーションzipは、`annofabcli project download <../project/download.html>`_ コマンドでダウンロードできます。

.. code-block::

    # アノテーションzipをダウンロードする。
    $ annofabcli project download simple_annotation --project_id prj1 --output annotation.zip



``--label_color`` には、ラベル名とRGB値の対応関係をJSON形式で指定してください。

.. code-block::
   :caption: label_color.json

    {"dog": [0,0,255],
      "cat": [255,0,0]
    }

アノテーション仕様画面で設定されている色を参照したい場合は、`annofabcli annotation_specs list_label_color <../annotation_specs/list_label_color.html>`_ コマンドの出力結果を使用してください。

.. code-block::

    $ annofabcli annotation_specs list_label_color --project_id prj1 --output label_color.json

``--image_size`` には、画像サイズを ``{width}x{height}`` の形式で指定してください。


.. code-block::

    $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
    --label_color  '{"dog":[0,0,255], "cat": [255,0,0]}' \
    --image_size 1280x720 \
    --output_dir out/


ディレクトリ ``out`` には、アノテーション画像が出力されます。ファイル名は ``{入力データID}.{拡張子}`` です。

.. code-block::

    out/
    ├── input_data_id_1.png
    ├── input_data_id_2.png
    ...


.. image:: write_annotation_image/output_image.png



.. warning::

    複数のタスクに同じ入力データが含まれている場合、出力されるアノテーション画像は上書きされます。


画像化対象の絞り込み
--------------------------
画像化対象のラベルを絞り込む場合は、``--label_name`` に画像化対象のラベル名を指定してください。


.. code-block::

    $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
    --label_color  '{"dog":[0,0,255]}' \
    --label_name dog \
    --image_size 1280x720 \
    --output_dir out/



画像化対象のタスクを絞り込む場合は、``--task_id`` に画像化対象のタスクのtask_idを指定してください。



.. code-block::
    :caption: task_id.txt

    task1
    task2
    ...


.. code-block::

    $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
    --label_color file://label_color.json \
    --task_id file://task_id.txt \
    --image_size 1280x720 \
    --output_dir out/


``--task_status_complete`` を指定すると、完了状態のタスクのみ画像化します。

.. code-block::

    $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
    --label_color file://label_color.json \
    --task_status_complete \
    --image_size 1280x720 \
    --output_dir out/



画像サイズの指定
--------------------------
プロジェクトに異なるサイズの画像が含まれている場合、``--image_size`` は使用できません。
替わりに、入力データ全件ファイルを読み込み、入力データごとに画像サイズを取得します。

入力データ全件ファイルは、以下のコマンドでダウンロードします。

.. code-block::

    $ annfoabcli project download input_data --project_id prj1 --output input_data.json


``--input_data_json`` に、入力データ全件ファイルを指定してください。入力データのプロパティ ``system_metadata.original_resolution`` を参照して画像サイズを取得します。

.. code-block::

     $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
         --input_data_json input_data.json \
         --label_color file://label_color.json \
         --output_dir out/



.. note::

    2020-12-23 以前に登録/更新した入力データには、``system_metadata.original_resolution`` に画像サイズ情報は格納されていません。


.. warning::

    入力データのメタデータのキーで画像サイズを取得するオプション ``--metadata_key_of_image_size`` は、廃止予定です。
    2020-12-24 以降に登録/更新した入力データは、プロパティ ``system_metadata.original_resolution`` に画像サイズが設定されるためです。


画像フォーマットの指定
--------------------------

デフォルトでは"png"画像が出力されます。画像フォーマットを指定する場合は、``--image_extension`` に出力される画像の拡張子を指定してください。


.. code-block::

    $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
    --label_color file://label_color.json \
    --image_extension bmp \
    --image_size 1280x720 \
    --output_dir out/


背景色の指定
--------------------------


デフォルトでは背景は黒色です。 ``--background_color`` に以下のようなフォーマットで色を指定すると、背景色を指定できます。

* ``rgb(173, 216, 230)``
* ``lightgrey``
* ``#add8e6``

サポートしているフォーマットは、`Pillow - ImageColor Module <https://pillow.readthedocs.io/en/stable/reference/ImageColor.html>`_ を参照してください。



.. code-block::

    $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
    --label_color file://label_color.json \
    --background_color "rgb(255,255,255)" \
    --image_size 1280x720 \
    --output_dir out/

Usage Details
=================================

.. argparse::
   :ref: annofabcli.filesystem.write_annotation_image.add_parser
   :prog: annofabcli filesystem write_annotation_image
   :nosubcommands:
   :nodefaultconst:


See also
=================================

* `アノテーションzipの構造 <https://annofab.com/docs/api/#section/Simple-Annotation-ZIP>`_
* `annofabcli project download <../project/download.html>`_
* `annofabcli annotation_specs list_label_color <../annotation_specs/list_label_color.html>`_


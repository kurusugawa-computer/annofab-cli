=================================
filesystem write_annotation_image
=================================

Description
=================================
アノテーションzip、またはそれを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成します。

画像化対象のアノテーションは、アノテーションデータの``_type`` が以下の場合です。

* ``BoundingBox`` （矩形）
* ``Points``  （ポリゴン or ポリライン）
* ``Segmentation`` （塗りつぶし）
* ``SegmentationV2`` （塗りつぶしv2）



Examples
=================================


基本的な使い方
--------------------------

``--annotation`` には、AnnoFabからダウンロードしたアノテーションzipか、アノテーションzipを展開したディレクトリを指定してください。
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

アノテーション仕様画面で設定されている色を参照したい場合は、``annofabcli annotation_specs list_label_color`` コマンドの出力結果を使用してください。
label_name(英名)とRGBの関係をJSONで出力します。出力された内容は、`write_annotation_image`ツールに利用します。出力内容は`Dict[LabelName, [R,G,B]]`です。

.. code-block::

    $ annofabcli annotation_specs list_label_color --project_id prj1 --output label_color.json

``--image_size`` には、画像サイズを ``{width}x{height}`` の形式で指定してください。


AnnoFabからダウンロードしたアノテーションzipを渡してください。`` には、AnnoFabからダウンロードしたアノテーションzipを渡してください。

 label_nameとRGBの関係をJSON形式で指定します。ex) `{"dog":[255,128,64], "cat":[0,0,255]}``file://`を先頭に付けると、JSON形式のファイルを指定できます。 (default: None)

    # label_nameとRGBを対応付けたファイルを生成する
    $ annofabcli annotation_specs list_label_color --project_id prj1 --output label_color.json

.. code-block::

    $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
    --label_color  '{"dog":[0,0,255], "cat": [255,0,0]}' \
    --image_size 1280x720 \
    --output_dir out/


ディレクトリ ``out`` には、ファイル名が入力データIDである画像ファイルが出力されます。名前がtask_idのディレクトリは出力されません。

.. code-block::

    out/
    ├── input_data_id_1.png
    ├── input_data_id_2.png
    ...


.. image:: write_annotation_image/output_image.png


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



画像形式？
--------------------------

デフォルトでは"png"画像が出力されます。画像フォーマットを指定する場合は、``--image_extension`` に出力される画像の拡張子を指定してください。


.. code-block::

    $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
    --label_color file://label_color.json \
    --image_extension bmp \
    --image_size 1280x720 \
    --output_dir out/



デフォルトでは背景画像は黒色です。 ``--background_color`` に以下のようなフォーマットで色を指定すると、背景画像を指定できます。

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


# 入力データのメタデータ"width", "height"に設定した画像サイズを参照して、アノテーション画像を生成する
$ annfoabcli project download input_data --project_id prj1 --output input_data.json
$ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
 --input_data_json input_data.json \
 --metadata_key_of_image_size width height \
 --label_color file://label_color.json \
 --output_dir /tmp/output
```



See also

* SImpleアノテーションの構造
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

``--annotation`` には、AnnoFabからダウンロードしたアノテーションzipを渡してください。
アノテーションzipは、`annofabcli project download <https://domain.invalid/>`_ コマンドでダウンロードできます。

.. code-block::

    # アノテーションzipをダウンロードする。
    $ annofabcli project download simple_annotation --project_id prj1 --output annotation.zip


    # label_nameとRGBを対応付けたファイルを生成する
    $ annofabcli annotation_specs list_label_color --project_id prj1 --output label_color.json


    # annotation.zip から、アノテーション画像を生成する
    $ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
    --image_size 1280x720 \
    --label_color file://label_color.json \
    --output_dir /tmp/output





``--input_data_id`` に削除対象入力データのinput_data_idを指定してください。

以下のコマンドは、``input_data_id.txt`` に記載されているinput_data_idに一致する入力データを削除します。

.. code-block::

    $ annofabcli input_data delete --project_id prj1 --input_data_id file://input_data_id.txt

デフォルトでは、タスクに使われている入力データを削除しません。
タスクに使われている入力データを削除するには、``--force`` を指定してください。


.. code-block::

    $ annofabcli input_data delete --project_id prj1 --input_data_id file://input_data_id.txt \
    --force

.. warning::

    タスクに使わている入力データを削除すると、削除対象の入力データに付与されたアノテーションを、AnnoFabのアノテーションエディタ画面で確認することができません。






### filesystem write_annotation_image
アノテーションzip、またはそれを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成します。
以下のアノテーションが画像化対象です。
* 矩形
* ポリゴン
* 塗りつぶし
* 塗りつぶしv2


```
# アノテーションzipをダウンロードする。
$ annofabcli project download simple_annotation --project_id prj1 --output annotation.zip


# label_nameとRGBを対応付けたファイルを生成する
$ annofabcli annotation_specs list_label_color --project_id prj1 --output label_color.json


# annotation.zip から、アノテーション画像を生成する
$ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
 --image_size 1280x720 \
 --label_color file://label_color.json \
 --output_dir /tmp/output

# label_nameがdogとcatのアノテーションのみ画像化する
$ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
 --image_size 1280x720 \
 --label_color '{"dog":[255,0,0], "cat":[0,255,0]}' \
 --label_name dog cat
 --output_dir /tmp/output

# annotation.zip から、アノテーション画像を生成する。ただしタスクのステータスが"完了"で、task.txtに記載れたタスクのみ画像化する。
$ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
 --image_size 1280x720 \
 --label_color file://label_color.json \
 --output_dir /tmp/output \
 --task_status_complete \
 --task_id file://task.txt


# 入力データのメタデータ"width", "height"に設定した画像サイズを参照して、アノテーション画像を生成する
$ annfoabcli project download input_data --project_id prj1 --output input_data.json
$ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
 --input_data_json input_data.json \
 --metadata_key_of_image_size width height \
 --label_color file://label_color.json \
 --output_dir /tmp/output
```

#### 出力結果（塗りつぶし画像）

![filesystem write_annotation_iamgeの塗りつぶし画像](readme-img/write_annotation_image-output.png)

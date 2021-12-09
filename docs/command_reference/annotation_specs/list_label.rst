==========================================
annotation_specs list_label
==========================================

Description
=================================
アノテーション仕様のラベル情報を出力します。




Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_specs list_label --project_id prj1

デフォルトでは最新のアノテーション仕様を出力します。過去のアノテーション仕様を出力する場合は、``--before`` または ``--history_id`` を指定してください。
history_idは、`annofabcli annotation_specs list_history <../annotation_specs/list_history.html>`_ コマンドで取得できます。

以下のコマンドは、最新より1つ前のアノテーション仕様を出力します。

.. code-block::

    $ annofabcli annotation_specs list_label --project_id prj1 --before 1


以下のコマンドは、history_idが"xxx"のアノテーション仕様を出力します。

.. code-block::

    $ annofabcli annotation_specs list_label --project_id prj1 --history_id xxx


出力結果
=================================

text出力
----------------------------------------------
以下のような、人が見てわかりやすい形式で出力します。

.. code-block::

    label_id    label_type    label_name_ja    label_name_en
        attribute_id    attribute_type    attribute_name_ja    attribute_name_ja
            choice_id    choice_name_ja    choice_name_en
            ...
        ...
    ...

.. code-block::

    $ annofabcli annotation_specs list_label --project_id prj1  --format text --output out.txt


.. code-block::
    :caption: out.txt

    15ba7932-24b9-4cf3-95bd-9bf6deede4fa	bounding_box	ネコ	Cat
        e6864d96-78fa-45f3-a786-6c8c900c92ae	flag	隠れ	occluded
        51e8c91f-5de1-450b-a0f3-94fec582f5ce	link	目のリンク	link-eye
        aff2855e-2e3d-47a2-8c27-c7652e4dfb2f	integer	体重	weight
        7e6a577a-3410-4c8a-9624-2904bb2e6666	comment	名前	name
        a63a0513-a96e-4c7c-8754-88a24fef9ca9	text	備考	memo
        649abf45-1ed7-459a-8282-a58228e9a302	tracking	object id	object id
    c754f724-5f8c-48eb-81ec-ea77e55efee7	polyline	足	leg
    f50aa88d-36c7-43f5-8728-247a49b4f4d8	point	目	eye
    108ce1f7-217b-43e9-a407-8d0ac6aad87e	segmentation	犬	dog
    2ffb4c74-106b-44ac-81ce-3c3df77518e0	segmentation_v2	人間	human
    ded52dcb-bcd6-4e77-9626-61e546f635d0	polygon	鳥	bird
    5ac0d7d5-6738-4c4b-a69a-cd583ff458e1	classification	気候	climatic
        896d7eeb-9c60-4fbf-b7c4-8f4209261049	choice	天気	weather
            c9615782-b872-4641-9be4-0fb4f905d966		晴	sunny
            553018a5-e594-4536-bc05-876fa6b48ed5		雨	rainy
        60caffa5-6300-4819-9a99-c43ce49008c2	select	気温	temparature
            89b3577d-a245-4b85-82ef-6569ecbf8ad7		10	10
            bdcd4d5b-cecc-4ec9-9038-d9284cd4f475		20	20
            9f3a0355-2cc8-412a-9129-3b62fa7b6ead		30	30
            2726336c-96d3-485b-9f96-7d4bcc97083b		40	40






JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs list_label --project_id prj1  --format pretty_json --output out.json

https://annofab.com/docs/api/#operation/getAnnotationSpecs APIのレスポンス（ ``AnnofationSpecsV1`` の ``labels`` キー）と同じです。

.. code-block::
    :caption: out.json

    [
        {
            "label_id": "728931a1-d0a2-442c-8e60-36c65ee7b878",
            "label_name": {
            "messages": [
                {
                "lang": "ja-JP",
                "message": "car"
                },
                {
                "lang": "en-US",
                "message": "car"
                }
            ],
            "default_lang": "ja-JP"
            },
            "keybind": [
            {
                "code": "Digit1",
                "shift": false,
                "ctrl": false,
                "alt": false
            }
            ],
            ...
        },
        ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_annotation_specs_label.add_parser
   :prog: annofabcli annotation_specs list_label
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli annotation_specs list_history <../annotation_specs/list_history.html>`_


:orphan:
# task list

## Description

## Examples

### タスクのフェーズやステータスなどで絞り込み
`--task_query`を指定すると、タスクのフェーズやステータスなどで絞り込めます。

`--task_query`に渡す値は、[getTasks API](https://annofab.com/docs/api/#operation/getTasks) のクエリパラメータとほとんど同じです。
さらに追加で、`user_id`, `previous_user_id` キーも指定できます。

以下のコマンドは、受入フェーズで完了状態のタスク一覧を出力します。

```
$ annofabcli task list --project_id prj1 \
 --task_query '{"status":"complete", "phase":"acceptance"}' 
```


差し戻されたタスクの一覧を出力します。

```
$ annofabcli task list --project_id prj1 --task_query '{"rejected_only": true}' 
```


過去の担当者が"user1"であるタスクの一覧を出力します。

```
$ annofabcli task list --project_id prj1 \
 --task_query '{"previous_user_id": "user1"}' 
```

metadataの`priority`が5であるタスク一覧を出力します。

```
$ annofabcli task list --project_id prj1 --task_query '{"metadata": "priority:5"}'
```


### タスクの担当者で絞り込み
タスクの担当者がuser1, user2であるタスクの一覧を出力します。

```
$ annofabcli task list --project_id prj1 \
 --user_id user1 user2 
```


### task_idで絞り込み
task_idが`task1`、`task2`であるタスクの一覧を出力します。


```
$ annofabcli task list --project_id prj1 --task_id task1 task2
```




## 出力結果
### CSV出力

```
$ annofabcli task list --project_id prj1 --format csv --output out.csv
```


### JSON出力

```
$ annofabcli task list --project_id prj1 --format pretty_json --output out.json
```

`out.json`の中身:

```
[ 
  {
    "project_id": "prj1",
    "task_id": "task1",
    "phase": "acceptance",
    "phase_stage": 1,
    "status": "complete",
    "input_data_id_list": [
      "input1"
    ],
    "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
    "histories_by_phase": [
      {
        "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
        "phase": "annotation",
        "phase_stage": 1,
        "worked": true,
        "user_id": "test_user_id",
        "username": "test_username"
      },
      ...
    ],
    "work_time_span": 8924136,
    "started_datetime": "2020-11-24T16:21:27.753+09:00",
    "updated_datetime": "2020-11-24T16:29:29.381+09:00",
    "sampling": null,
    "metadata": {},
    "user_id": "test_user_id",
    "username": "test_username",
    "worktime_hour": 2.4789266666666667,
    "number_of_rejections_by_inspection": 0,
    "number_of_rejections_by_acceptance": 1
  },
  ...
]

```

### task_idの一覧を出力

```
$ annofabcli task list --project_id prj1 --format task_id_format --output task_id.txt
```

`task_id.txt`の中身: 

```
task1
task2
...
```
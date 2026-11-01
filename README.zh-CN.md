# iris-kaggle-import

[English](README.md)

使用一行 ObjectScript 将 Kaggle 数据集导入 InterSystems IRIS。每个 CSV 或 Parquet 文件生成一张表。项目对应 [Community Bounty 第三轮](https://community.intersystems.com/post/community-bounty-program-idea-application-%E2%80%94-round-3-live)的 [DPI-I-1012](https://ideas.intersystems.com/ideas/DPI-I-1012) 创意。

```objectscript
do ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness")
```

## 快速开始

需要 Docker、Compose v2 和互联网连接。克隆项目并启动容器：

```bash
git clone https://github.com/boanerges1227/iris-kaggle-import.git
cd iris-kaggle-import
docker compose up -d --build --wait
docker compose exec iris iris session IRIS -U USER
```

在打开的 IRIS 终端中执行上面的 ObjectScript 示例。容器使用 21975 端口（SQL）和 52997 端口（Web），命名空间为 `USER`，登录信息为 `_SYSTEM` / `SYS`；这些默认凭据只适合本地评估。

Compose 默认使用公开的 `intersystems/irishealth-community:2026.2` 镜像；可通过 `IRIS_IMAGE` 指定其他兼容镜像。项目已在 ARM64 的 IRIS Community 2026.1 和 IRIS for Health Community 2026.2 上测试，其他版本尚未验证。

## 使用方法

```text
Load(handle, target="", limit=0, mode="replace")
```

| 参数 | 默认值 | 说明 |
|---|---|---|
| `handle` | 必填 | `owner/name` 获取最新版本；`owner/name/versions/N` 指定版本 |
| `target` | `KaggleData.<数据集名>` | `schema.表前缀`；各文件的表名为 `<前缀>_<文件名>` |
| `limit` | `0` | 每个文件的最大导入行数；0 表示全部 |
| `mode` | `replace` | `replace` 替换、`append` 追加、`fail` 在表已存在时失败 |

方法返回 JSON，包含状态、各表行数、列类型和未导入文件。用 `write` 可直接查看返回值：

```objectscript
write ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness","Demo.happy",100),!
write ##class(dc.kaggleloader.Loader).Info("unsdsn/world-happiness"),!
write ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness/versions/2","Demo.happy",0,"fail"),!
```

`Info` 会下载数据集并列出文件，但不会导入数据。

## Kaggle 身份认证

多数公开数据集无需凭据。对于需要同意条款或认证的数据集，可在启动容器时提供 Kaggle API 凭据：

```bash
KAGGLE_USERNAME=your_user KAGGLE_KEY=your_key docker compose up -d --wait
# 或者
KAGGLE_API_TOKEN=your_token docker compose up -d --wait
```

在 [Kaggle 设置页面](https://www.kaggle.com/settings)的 API 部分创建凭据。不要将凭据提交到版本库。

## 导入规则与限制

- 每个 `.csv` 或 `.parquet` 文件对应一张表；其他文件列在 `notImported` 中。
- CSV 按整列推断：整数为 `BIGINT`，浮点数为 `DOUBLE`，`true`/`false` 为 `BIT`，其他为 `VARCHAR(4000)`。前导零保留为文本，空字段存为 NULL。
- CSV 行字段多于表头时返回错误；字段不足时补 NULL。
- Parquet 的整数、浮点、布尔、日期和时间戳分别映射为 `BIGINT`、`DOUBLE`、`BIT`、`DATE` 和 `TIMESTAMP`；嵌套值转换为 JSON 文本，其他类型存为 `VARCHAR(4000)`。
- 表名和列名进行规范化；重复列名增加数字后缀。不同文件映射到同一表名时，导入前返回错误。
- 默认每张表最多 1,000,000 行，每个文件最多 100 MB，可分别通过 `KAGGLE_MAX_ROWS` 和 `KAGGLE_MAX_FILE_MB` 调整。限制在下载和解压后检查，不能限制下载流量或解压空间。
- 导入不是原子操作。出错时先前导入的表或部分行可能保留；`replace` 可能先删除已有表。建议使用专用 schema，并检查返回结果。

## 在现有 IRIS 中安装

项目需要 Embedded Python、IPM、网络连接，以及向实例 Python 目录安装依赖的权限。在目标实例中执行：

```objectscript
zpm "load /path/to/iris-kaggle-import"
```

IPM 会根据 `requirements.txt` 安装 `kagglehub` 和 `pyarrow`，并复制项目 Python 模块。本地 `zpm load` 已在干净的 IRIS Community 2026.1 ARM64 实例中验证，并通过真实数据集导入；注册表安装命令需要先发布软件包。

## 测试

```bash
./tests/test.sh
```

验收测试访问 Kaggle，并在 `KaggleData` schema 中创建和替换测试表，请使用可丢弃的测试实例。回归测试：

```bash
docker compose exec -T iris python3 -m unittest discover -s /home/irisowner/dev/tests -p test_regressions.py -v
python3 -m unittest discover -s tests -p test_acceptance_parser.py -v
```

在独立容器中，固定版本 `unsdsn/world-happiness/versions/2` 已导入 5 张表，共 782 行；Parquet 的替换和追加也已做 IRIS 数据往返验证。

## 许可证

项目采用 MIT 许可证。不包含数据集；各数据集仍受其自身许可证和使用条款约束，导入或分享前请先核对。

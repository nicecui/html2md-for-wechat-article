# Python + OpenTelemetry，观测你的特斯拉！

开源、云原生、分布式时序数据库

161篇原创内容

本样例较长，将分为两个部分，此文为第 1 部分：从 Tesla Owner API 导出指标到 Greptime。

# 项目概述

OpenTelemetry 作为一套行业领先的监控应用和网络的统一标准，能帮助开发者轻松捕获和跟踪关键数据，深入了解系统的运行状态。如果你还不太了解 OpenTelemetry 及其应用场景，可以参考我们之前的博文，了解相关基础知识。

本
篇文章详细展示了使用 OpenTelemetry 监控 Tesla Model 3 的充电与驾驶数据的例子。该项目流程相对简洁：通过 
OpenTelemetry 对 Python 服务进行监控，并连接 Tesla Owner API，每 5 
分钟收集一次指标数据。此外，项目还包含一个使用 Docker 托管的 GreptimeDB 
实例，作为这个监控应用程序的目标数据库，用于接收并存储导出的指标数据。

# 应用程序的设置

首先，从 Greptime 的 demo 仓库中下载相关代码：


```
`git clone https://github.com/GreptimeTeam/demo-scene.git`
`cd demo-scene/ev-open-telemetry`

```

该项目通过将 Python 服务部署在其专属的 Docker 容器中，以最少的依赖运行。因此，如果还未安装 Docker，需要先安装 Docker。

通过以下命令验证 Docker 是否已正确安装：


```
`docker -v`
`=> Docker version ...`

```

## 设置 Python 环境

如果希望直接在本地运行代码而不使用 Docker，请确保正确设置 Python 环境：

- 设置 Python 依赖管理系统：Poetry

- 设置 Python 版本管理系统：pyenv

- 使用命令下载 Python 3.9：pyenv install 3.9

- 构建带有固定依赖的虚拟环境来构建项目：在./ev-open-telemetry/ev-observer目录下运行poetry install

## 项目依赖文件

`pyproject.toml`文件中的这些依赖项是项目的核心，OpenTelemetry 模块处理数据采集和传输，Tesla API 客户端获取实际的车辆数据，pydantic 则确保数据格式的准确性和一致性。

依赖文件地址：https://github.com/GreptimeTeam/demo-scene/blob/main/ev-open-telemetry/ev_observer/pyproject.toml

1. OpenTelemetry 标准模块：收集和处理应用程序的性能和运行时数据（即"指标"）。

- 捕获指标：监控 Tesla Model 3 充电和驾驶数据。

- 格式化数据：将捕获的指标数据打包为 OpenTelemetry 协议支持的 HTTP/OTLP 格式。

- 发送数据：通过 HTTP 将数据发送到兼容 OTLP 的后端（这里是 GreptimeDB）。

2. Python Tesla API 客户端：这个依赖项是 Tesla 车辆的 API 客户端，用来从 Tesla Owner API 获取实时数据（例如电池状态、驾驶统计等）。这个 API 客户端直接与 Tesla 的服务通信，确保应用程序可以通过 Python 轻松地获取车内的数据。

3. Pydantic 库：Pydantic 是一个用于验证和解析数据的 Python 库，帮助确保代码中的类型提示（type hints）被正确遵循。它使得数据模型更清晰，并提供类型安全的环境，减少潜在的错误。

# 如何使用 OpenTelemetry

OpenTelemetry
 的监控库为开发者提供了一些 hooks，可以用来与 OpenTelemetry API 交互并捕获感兴趣的指标数据。要设置 
OpenTelemetry 
的监控功能，首先需要进行一些基础配置（boilerplate）。完成这些配置后，用户将创建一个计量器（meter），用于获取实际用于捕获遥测指标
的工具（instruments）。

## 创建 Meter

Instruments 是通过 Meter 获取的。计量器采集数据的规则（例如多长时间读取一次数据、将数据导出到哪里）是通过在 MeterProvider 中配置 Readers 来完成的。

## 配置步骤

- 首先，用户需要配置 exporter 和 reader，并将它们作为参数传递来初始化 MeterProvider；

- 使用配置好的 provider 设置全局的指标监控对象；

- 从这个全局监控对象中获取一个 Meter；

- 使用这个 Meter 创建 Instruments，这些 Instruments 提供了监控数据的接口。

## 修改配置

如果想修改例如多长时间导出一次指标数据、如何过滤/采样读取的数据，或者数据导出到哪里，这些配置都是在`Meter`初始化过程中完成的。

在本文的这个例子中，我们初始化配置了`PeriodicExportingMetricReader`，以`SCRAPE_INTERVAL`间隔的时间（默认为 300 秒）抓取一次数据，并通过`OTLPMetricExporter`将这些数据导出到我们的 GreptimeDB OTLP 后端。

Meter 的配置是在文件`ev-open-telemetry/ev_observer/ev_observer/init.py`[1] 中完成的。

## 创建 Instruments

现在我们已经了解了如何创建 Meter，接下来将介绍如何使用 Meter 来创建 Instruments 并通过它捕获指标将数据写入数据库。

这个过程可以同步或异步进行，这里我们采用异步收集方式。要设置异步收集，需通过 Meter 创建异步工具，并传入回调函数，每次读取数据时该回调函数都会被执行。

设置一个 Instrument 样例代码如下所示：


```
`def cpu_time_callback(options: CallbackOptions) -> Iterable[Observation]:`
`    observations = []`
`    ``with`` open(``"/proc/stat"``) ``as`` procstat:`
`        procstat.readline()  ``# skip the first line`
`        ``for`` line ``in`` procstat:`
`            ``if`` ``not`` line.startswith(``"cpu"``): ``break`
`            cpu, *states = line.split()`
`            observations.append(Observation(int(states[``0``]) // ``100``, {``"cpu"``: cpu, ``"state"``: ``"user"``}))`
`            observations.append(Observation(int(states[``1``]) // ``100``, {``"cpu"``: cpu, ``"state"``: ``"nice"``}))`
`            observations.append(Observation(int(states[``2``]) // ``100``, {``"cpu"``: cpu, ``"state"``: ``"system"``}))`
`            ``# ... other states`
`    ``return`` observations`

`meter.create_observable_counter(`
`    ``"system.cpu.time"``,`
`    callbacks=[cpu_time_callback],`
`    unit=``"s"``,`
`    description=``"CPU time"`
`)`

```

上述代码段通过已配置的 Meter 创建了一个名为`system.cpu.time`的 Instrument。在创建 Instrument 时，传入的`cpu_time_callback`回调函数会在初始化时被指定。然后，根据在`MetricsProvider`中配置的参数，`PeriodicMetricReader`会每隔 N 毫秒调用这个回调函数，采集系统的 CPU 时间数据。这个配置过程在之前提到的`init.py`文件中有记录。

## 封装 Instruments

手动为每个工具设置和管理非常繁琐，所以开发者创建了一个名为`MetricCollector`的基类。这个基类自动帮助我们生成这些工具，并创建回调函数，用来读取数据并将其发送给 OpenTelemetry。

`MetricCollector`的主要任务是：初始化这些工具，然后创建一些“回调函数”（用来定期读取数据）。这些回调函数被设计成能自动读取`MetricCollector`中最新的属性值，保证采集的是最新的数据并发送给 OpenTelemetry。

封装 OpenTelemetry 工具创建过程可参见`ev-open-telemetry/ev_observer/ev_observer/metrics.py`[2]。

举个例子，代码中的`ChargingState`类负责捕获特斯拉的电池电量和充电情况。通过在属性字段上加一个特殊的标记（`custom_tag="metric"`），告诉`MetricCollector`为这些属性创建工具，方便读取这些数值并进行监控。


```
`class ChargeState(MetricCollector):`
`    battery_level: Optional[int] = Field(``None``, custom_tag=``"metric"``)`
`    charge_energy_added: Optional[float] = Field(``None``, custom_tag=``"metric"``)`
`    charge_miles_added_ideal: Optional[float] = Field(``None``, custom_tag=``"metric"``)`
`    charge_miles_added_rated: Optional[float] = Field(``None``, custom_tag=``"metric"``)`
`    ...`
`    charging_state: Optional[str] = ``None`

```

# 实现 OpenTelemetry 数据收集过程

要实现 OpenTelemetry 数据的收集过程，需要关注的代码部分是两个模块：`EVMetricData`（用来处理电动车的指标数据）和`AbstractVehicleFetcher`（用来获取车辆相关数据的抽象接口）。

通过更新这两个模块并配置`VehicleInstrumentor`以使用所需的`VehicleFetcher`，系统就能够顺利收集特定车辆的指标数据，并将这些数据发送到 GreptimeDB 实例中。

下图展示了整个数据收集过程所涉及的组件：

## 确定要收集的指标

`EVMetricData`是一个管理多个负责读取和导出指标数据的`MetricCollector`的类，同时也负责初始化所有 Instruments 并更新类中的值。除了收集数据，它还可以通过`attributes`属性为数据添加更多信息，比如本例中我们给收集的指标打上车名的标签。

`DriveState`和`ChargeState`是两个子类，继承自`MetricsProvider`，这个类帮助创建 Instrument。如果想收集更多的指标，只需创建另一个子类，并将其加入到`EvMetricsData`类中即可。这使得扩展和增加监控指标变得非常容易。

项目中收集的所有 EV 指标可见：https://
github.com/GreptimeTeam/demo-scene/blob/
cfee3e09e97311049c7df454e1a688a9a67071ea/ev-open-telemetry/ev_observer/
ev_observer/metrics.py#L57-L121

# 用 Python API 监控特斯拉

特斯拉 API 允许车主通过编程的方式查看车辆信息，甚至可以控制车辆。我们使用这个 API 来实现一个叫做`TeslaMetricFetcher`的抽象类，它负责获取车辆的各种数据。

这个数据获取逻辑被封装在一个叫做`AbstractVehicleDataFetcher`的实现中。这个抽象类需要返回一个包含车辆指标的对象`EVMetrics`，之后`VehicleInstrumentor`类会定期刷新这些数据（我们将在下一小节展开）。这样的设计让我们以后可以轻松地添加其他电动车的监控指标，只需修改和刷新函数即可。

抽象基类及其特斯拉实现代码见此：https://
github.com/GreptimeTeam/demo-scene/blob/
cfee3e09e97311049c7df454e1a688a9a67071ea/ev-open-telemetry/ev_observer/
ev_observer/vehicle.py#L61-L86

车辆状态和刷新周期的主要管理者是`VehicleInstrumentor`。`VehicleInstrumentor`包含一个`AbstractVehicleDataFetcher`实例和一个`EVMetricData`实例。`VehicleInstrumentor`类负责设置仪器，并通过`fetcher`保持车辆数据的更新。

VehicleInstrumentor 代码可在此查看：https://
github.com/GreptimeTeam/demo-scene/blob/
cfee3e09e97311049c7df454e1a688a9a67071ea/ev-open-telemetry/ev_observer/
ev_observer/vehicle.py#L46-L58

# 运行程序

如
上所述，该项目使用 Docker 实现了“零依赖”的运行环境，用户无需配置复杂的依赖项就能快速启动项目。Docker Compose 
文件配置了整个网络，其中包括特斯拉的数据采集模块、用以存储指标数据的 GreptimeDB 数据库，以及用来可视化这些数据的 Grafana 
仪表盘。

用于容器化应用的 Docker Compose 文件可见：https://github.com/GreptimeTeam/demo-scene/blob/main/ev-open-telemetry/docker-compose.yml

要运行 Python 数据采集过程，你需要有特斯拉的有效账号，并且车辆必须已经注册。接着，你需要用这些登录信息来验证你的账号，项目运行时会提示你输入这些信息以完成认证。


```
`TESLA_USER_EMAIL={Your_Tesla_Email} docker compose up -d && \`
`while`` [ ``"$(docker inspect -f '{{.State.Running}}' ev-open-telemetry-ev_observer-1)"`` != ``"true"`` ]; do`
`  echo ``"Waiting for container ev-open-telemetry-ev_observer-1 to be up..."`
`  sleep ``1`
`done && docker logs ev-open-telemetry-ev_observer``-1`` & docker attach ev-open-telemetry-ev_observer``-1`

```

## 特斯拉身份验证流程

当容器启动后，日志中会显示以下信息：


```
`Open this URL to authenticate: `
`https://auth.tesla.com/oauth2/v3/authorize?...`

```

在浏览器中打开此链接，并使用特斯拉账户信息登录，成功验证后，将被定向到一个空白页面。将浏览器地址栏中的 URL 复制粘贴到终端中，以通过令牌完成身份验证。一旦完成这个步骤，生成的`cache.json`文件将使用刷新令牌来保持认证会话有效，直到容器运行结束。

应用成功运行后，特斯拉车辆数据将开始流入本地 Docker 容器中托管的 GreptimeDB 实例中。

# 设置 GreptimeDB 作为 OpenTelemetry 存储后端

OpenTelemetry
 的一个重要优势在于它的声明式语义标准，许多数据库都支持这一标准用于传输数据。我们使用 GreptimeDB 作为 OpenTelemetry 
的后端来捕获电动汽车（EV）的指标，用户也可以选择任何兼容 OpenTelemetry 的后端来捕获数据。

GreptimeDB 支持 Postgres 的协议（以及其他多种协议），支持使用常规的 Postgres 客户端来查询数据。在构建容器后，按照以下步骤来验证数据捕获情况：

1. 通过 Postgres 客户端连接到 GreptimeDB


```
`psql -h ``0.0``.0``.0`` -p ``4003`` -d public`

```

成功连接到 GreptimeDB 后，您可以在自动生成的表中查看所有已收集的数据。这些表会根据收集的指标自动创建并存储相关数据。

在 Postgres 客户端中运行相关查询：


```
`SELECT table_schema, table_name`
`public-> FROM information_schema.tables`
`=>`
` table_schema |               table_name`
`--------------+----------------------------------------`
` public       | chargestate_charge_rate`
` public       | chargestate_battery_range`
` public       | drivestate_power`
` public       | chargestate_max_range_charge_counter`
` public       | chargestate_charger_pilot_current`
` public       | chargestate_minutes_to_full_charge`
` public       | drivestate_native_location_supported`
` public       | chargestate_charge_limit_soc_max`
` public       | chargestate_charge_limit_soc_min`
` public       | chargestate_timestamp`
` public       | chargestate_charge_current_request`
` public       | chargestate_charger_voltage`
` public       | chargestate_ideal_battery_range`
` public       | chargestate_usable_battery_level`
` public       | drivestate_heading`
` public       | chargestate_time_to_full_charge`
` public       | drivestate_latitude`
` public       | chargestate_charge_miles_added_ideal`
` public       | drivestate_native_longitude`
` public       | drivestate_gps_as_of`
` public       | chargestate_est_battery_range`
` public       | chargestate_charge_miles_added_rated`
` public       | chargestate_charge_current_request_max`
` public       | chargestate_charge_limit_soc`
` public       | drivestate_timestamp`
` public       | chargestate_charger_power`
` public       | chargestate_battery_level`
` public       | drivestate_native_latitude`
` public       | chargestate_charge_limit_soc_std`
` public       | chargestate_charge_energy_added`
` public       | chargestate_charger_actual_current`
` public       | drivestate_longitude`
` public       | chargestate_charge_amps`
`(``33`` rows)`

```

进一步查询分析数据：


```
`SELECT vehicle_id, greptime_timestamp, greptime_value`
`FROM chargestate_battery_range`
`ORDER BY greptime_timestamp DESC`
`LIMIT ``10``;`
`=>`
`vehicle_id |     greptime_timestamp     | greptime_value`
`------------+----------------------------+----------------`
` Ju         | ``2024``-10``-08`` ``00``:``13``:``49.145132`` |         ``117.02`
` Ju         | ``2024``-10``-08`` ``00``:``12``:``49.136252`` |         ``117.02`
` Ju         | ``2024``-10``-08`` ``00``:``11``:``49.127737`` |         ``117.02`
` Ju         | ``2024``-10``-08`` ``00``:``10``:``49.115796`` |         ``117.02`
` Ju         | ``2024``-10``-08`` ``00``:``09``:``49.098576`` |         ``117.02`
` Ju         | ``2024``-10``-08`` ``00``:``08``:``49.085364`` |         ``117.02`
` Ju         | ``2024``-10``-08`` ``00``:``07``:``49.072459`` |         ``117.02`
` Ju         | ``2024``-10``-08`` ``00``:``06``:``49.055776`` |         ``117.02`
` Ju         | ``2024``-10``-08`` ``00``:``05``:``49.042333`` |          ``117.6`
` Ju         | ``2024``-10``-08`` ``00``:``04``:``49.022890`` |          ``117.6`

```

GreptimeDB
 对 OpenTelemetry 协议的实现使得指标数据的收集更加流畅便捷。由于 OpenTelemetry 
提供的标准化规范，用户可以轻松在不同的数据库提供商之间切换，从而避免在监控基础设施中受到特定厂商的绑定限制（vendor lock-in）。

### 下期预告：在 Grafana 中可视化 OpenTelemetry 指标

在
下一篇文章中，我们将展示如何使用 Grafana 对车辆数据进行可视化。通过 OpenTelemetry 等标准，以及 GreptimeDB 和
 Python SDK 等工具，捕获电动车的时间序列数据变得高效、可扩展。使用兼容 OpenTelemetry 的后端，将这些数据在像 
Grafana 这样的可视化工具中展示，也将变得轻松而直观。

# Reference

[1] https://github.com/GreptimeTeam/demo-scene/blob/main/ev-open-telemetry/ev_observer/ev_observer/init.py

[2] https://github.com/GreptimeTeam/demo-scene/blob/main/ev-open-telemetry/ev_observer/ev_observer/metrics.py

# 关于 Greptime

Greptime
 格睿科技专注于为可观测、物联网及车联网等领域提供实时、高效的数据存储和分析服务，帮助客户挖掘数据的深层价值。目前基于云原生的时序数据库 
GreptimeDB 已经衍生出多款适合不同用户的解决方案，更多信息或 demo 展示请联系下方小助手（微信号：greptime）。欢迎对开源感兴趣的朋友们参与贡献和讨论，从带有 good first issue 标签的 issue 开始你的开源之旅吧～期待在开源社群里遇见你！添加小助手微信即可加入“技术交流群”与志同道合的朋友们面对面交流哦~





Star us on GitHub Now:https://github.com/GreptimeTeam/greptimedb官网：https://greptime.cn/文档：https://docs.greptime.cn/Twitter:https://twitter.com/GreptimeSlack:https://greptime.com/slackLinkedIn:https://www.linkedin.com/company/greptime/

往期精彩文章：





👇 点击下方阅读原文，立即体验 GreptimeDB！



# 







Search「undefined」网络结果



暂无留言



Scan to Follow

当前内容可能存在未经审核的第三方商业营销信息，请确认是否继续访问。

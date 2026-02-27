# 虚拟串口模拟器测试指南

本指南说明如何在 Quantix 项目中使用虚拟串口模拟器进行测试。

## 快速测试流程

### 步骤 1: 启动虚拟串口模拟器

```bash
python virtual_serial_simulator.py
```

### 步骤 2: 创建虚拟串口对

选择菜单 `1. 创建虚拟串口对`

```
[Windows模式] Creating virtual serial pair:
  Port A: TCP_PORT_20000 (模拟)
  Port B: TCP_PORT_20001 (模拟)
```

### 步骤 3: 选择 Modbus Slave 模式

```
选择工作模式:
 1. Modbus RTU Slave (默认)
 2. Modbus RTU Master
 3. 原始串口

选择: 1
```

### 步骤 4: 配置自动发送（可选）

进入运行界面后，输入 `a` 配置自动发送：

```
> a

═══════════════ Auto Send ═══════════════
 Status: OFF
═══════════════════════════════════════

Options:
 1. Start auto send
 2. Stop auto send
 3. Set interval (seconds)
 4. Set data (HEX)
 5. Quick presets

选择: 5
> 1        # 选择 Modbus 读保持寄存器预设
> 1        # 启动自动发送
> 3        # 设置间隔
> 0.5      # 0.5秒发送一次
```

### 步骤 5: 在 Quantix 项目中创建测试设备

#### 方案 A: 使用 com0com 创建真实虚拟串口（推荐 Windows）

1. 安装 [com0com](https://sourceforge.net/projects/com0com/)
2. 创建串口对（如 COM10 ↔ COM11）
3. 虚拟串口模拟器连接到 COM10
4. Quantix 项目连接到 COM11

#### 方案 B: 使用 TCP 端口（跨平台）

修改你的 Quantix 项目代码，支持连接到 TCP 端口而不是串口。

### 步骤 6: 使用测试模板

在 Quantix 项目的设备模板页面，导入以下模板：

#### 模板 1: 标准单寄存器

```json
{
  "name": "测试设备-Modbus RTU 虚拟串口",
  "protocol_type": "modbus_rtu",
  "variables": [
    { "name": "slave_id", "type": "int", "default": 1, "label": "从站地址" },
    { "name": "weight_addr", "type": "int", "default": 0, "label": "重量寄存器起始地址" },
    { "name": "scale", "type": "float", "default": 100, "label": "重量缩放系数" }
  ],
  "steps": [
    {
      "id": "read_weight",
      "name": "读取重量",
      "trigger": "poll",
      "action": "modbus.read_holding_registers",
      "params": {
        "slave_id": "${slave_id}",
        "address": "${weight_addr}",
        "count": 1
      },
      "parse": {
        "type": "expression",
        "expression": "registers[0] / scale"
      }
    }
  ],
  "output": {
    "weight": "${steps.read_weight.result}",
    "unit": "kg"
  }
}
```

#### 模板 2: 双寄存器32位重量

```json
{
  "name": "测试设备-Modbus RTU 双寄存器重量",
  "protocol_type": "modbus_rtu",
  "variables": [
    { "name": "slave_id", "type": "int", "default": 1, "label": "从站地址" },
    { "name": "weight_addr", "type": "int", "default": 0, "label": "重量寄存器起始地址" },
    { "name": "scale", "type": "float", "default": 1000, "label": "重量缩放系数" }
  ],
  "steps": [
    {
      "id": "read_weight",
      "name": "读取重量",
      "trigger": "poll",
      "action": "modbus.read_holding_registers",
      "params": {
        "slave_id": "${slave_id}",
        "address": "${weight_addr}",
        "count": 2
      },
      "parse": {
        "type": "expression",
        "expression": "(registers[0] * 65536 + registers[1]) / scale"
      }
    }
  ],
  "output": {
    "weight": "${steps.read_weight.result}",
    "unit": "kg"
  }
}
```

### 步骤 7: 创建设备实例

在 Quantix 项目中创建设备时，设置连接参数：

```json
{
  "port": "COM11",           // 或 "/dev/ttyUSB0" (Linux/macOS)
  "baudrate": 9600,
  "bytesize": 8,
  "parity": "N",
  "stopbits": 1,
  "timeout": 1
}
```

### 步骤 8: 观察测试结果

1. 虚拟串口模拟器会显示收发的 Modbus 数据包
2. Quantix 项目前端会显示实时重量数据
3. 重量值会根据虚拟串口的数据模式变化（固定/随机/正弦波/随机游走）

## 调试技巧

### 查看虚拟串口模拟器统计信息

```
> l

═══════════════ Statistics ═══════════════
 RX: 125 packets
 TX: 125 packets
 Mode: Modbus RTU Slave
 Slave Address: 1
 Data Pattern: Random walk
 Auto Send: ON
   Interval: 0.5s
   Data: 01 03 00 00 00 01
═══════════════════════════════════════
```

### 更改数据模式

```
> c
> 4        # 选择数据模式配置

Data patterns:
 1. Fixed value
 2. Random
 3. Sine wave
 4. Random walk

选择: 3    # 正弦波模式，数据会平滑变化
```

### 手动发送测试数据

```
> s
输入HEX数据: 01 03 00 00 00 02
```

## 常见问题

### Q: 设备一直显示 offline

**A**: 检查以下几点：
1. 虚拟串口模拟器是否正在运行且在 Slave 模式
2. 串口参数是否匹配（波特率、数据位、校验位、停止位）
3. 从站地址是否一致（默认都是 1）
4. 串口是否被其他程序占用

### Q: 重量数据不变化

**A**:
1. 检查虚拟串口模拟器的数据模式，改为 "Random" 或 "Random walk"
2. 确认自动发送已开启（`> a > 1`）
3. 查看统计信息确认 RX/TX 数据包在增加

### Q: 重量数值异常大或异常小

**A**:
1. 检查模板中的 `scale` 参数
2. 如果是双寄存器模板，确认高低位组合方式
3. 尝试不同的缩放系数（100, 1000, 10000）

### Q: Windows 下如何测试？

**A**:
1. 下载安装 com0com: https://sourceforge.net/projects/com0com/
2. 运行 setupc 安装后，打开 setupc 图形界面
3. 点击 "Add Pair" 创建串口对
4. 记住两个串口名称（如 CNCA0 ↔ CNCB0，对应 COM11 ↔ COM12）
5. 虚拟串口模拟器连接到 COM11
6. Quantix 项目连接到 COM12

## 测试场景示例

### 场景 1: 测试基本轮询功能

```
虚拟串口配置:
- 模式: Modbus Slave
- 从站地址: 1
- 数据模式: Random walk

Quantix 设备配置:
- 使用模板: "测试设备-Modbus RTU 虚拟串口"
- slave_id: 1
- weight_addr: 0
- scale: 100

预期结果:
- 前端显示重量数据持续小幅度变化
- 模拟器显示周期性的 Modbus 请求/响应
```

### 场景 2: 测试 32 位重量值

```
虚拟串口配置:
- 模式: Modbus Slave
- 数据模式: Sine wave (正弦波)

Quantix 设备配置:
- 使用模板: "测试设备-Modbus RTU 双寄存器重量"
- slave_id: 1
- weight_addr: 0
- scale: 1000

预期结果:
- 重量值按正弦波平滑变化
- 数值范围约 0-65 kg
```

### 场景 3: 测试异常处理

```
虚拟串口配置:
- 在运行时关闭 (Ctrl+C 然后继续)

Quantix 预期行为:
- 设备状态变为 offline
- 重量保持最后有效值或显示 null
- 模拟器重新启动后设备自动恢复 online
```

## 预设的 Modbus 测试数据

虚拟串口模拟器内置以下预设：

| 预设 | HEX 数据 | 说明 |
|------|----------|------|
| 1 | `01 03 00 00 00 01` | 读保持寄存器 x01 |
| 2 | `01 04 00 00 00 01` | 读输入寄存器 x01 |
| 3 | `01 01 00 00 00 08` | 读线圈 x08 |
| 4 | `AA BB CC DD` | 自定义测试模式 |

你可以根据这些预设配置对应的模板。

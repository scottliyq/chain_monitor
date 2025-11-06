# Lista Withdraw 音频提示功能说明

## 功能概述

当检测到可取出金额大于或等于配置的金额时，程序会自动播放 `resource/alert.mp3` 提示音。

## 音频控制

### 开启音频（默认）

```bash
# 默认情况下音频提示是开启的
python lista_withdraw.py --amount 0.5 --once
```

### 关闭音频

使用 `--no-sound` 参数可以关闭音频提示：

```bash
# 单次执行，关闭音频
python lista_withdraw.py --amount 0.5 --once --no-sound

# 循环执行，关闭音频
python lista_withdraw.py --interval 60 --amount 0.5 --no-sound
```

## 使用示例

### 示例 1：开启音频的单次执行
```bash
python lista_withdraw.py --amount 0.001 --once
```
**结果**：当满足条件时，会播放提示音并显示：
```
🎉 检测到可取出金额 (1.713720) >= 配置金额 (0.001000)
🔔 播放提示音...
🔔 播放提示音: alert.mp3
```

### 示例 2：关闭音频的单次执行
```bash
python lista_withdraw.py --amount 0.001 --once --no-sound
```
**结果**：满足条件时不播放提示音，只显示：
```
🎉 检测到可取出金额 (1.713720) >= 配置金额 (0.001000)
🔇 音频提示已关闭
```

### 示例 3：循环执行，关闭音频
```bash
python lista_withdraw.py --interval 60 --amount 0.5 --no-sound
```

## 配置信息显示

运行时会显示音频提示的状态：

```
⚙️ 配置信息:
   检查间隔: 60 秒
   取出金额: 0.5
   运行模式: 循环执行
   音频提示: 开启/关闭  ← 这里会显示当前状态
```

## 技术说明

- 音频播放使用非阻塞方式，不会影响程序继续执行
- 支持 macOS、Linux、Windows 多平台
- macOS 使用 `afplay` 命令
- Linux 支持 `mpg123`、`ffplay` 等播放器
- Windows 使用 `winsound` 模块
- 如果音频播放失败，程序会继续正常运行，只显示警告信息

## 故障排除

如果音频无法播放：
1. 检查 `resource/alert.mp3` 文件是否存在
2. 确认系统有可用的音频播放器
3. 查看日志中的警告信息
4. 使用 `--no-sound` 参数禁用音频功能

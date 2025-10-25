# 🏷️ 地址标签集成功能使用指南

## 📋 功能概述

代币交易分析器现在已经集成了SQLite地址标签查询功能！在生成分析结果时，系统会自动为每个地址调用`sqlite_address_querier.py`中的`get_address_label`方法来获取标签信息。

## 🔧 功能特性

### ✅ 自动地址标签查询
- **多级查询策略**: 地址常量 → SQLite缓存 → 外部API → 默认值
- **智能缓存**: Unknown结果会被保存但不阻止重新查询
- **多网络支持**: Ethereum, Polygon, BSC
- **增强输出**: 分析结果包含详细的地址标签信息

### ✅ 增强的输出格式

#### JSON输出增强
```json
{
  "address_labels_enabled": true,
  "filtered_contracts": [
    {
      "rank": 1,
      "address": "0x...",
      "name": "Original Name",
      "address_label": "Binance Hot Wallet",
      "address_type": "exchange",
      "label_source": "constants",
      "transaction_count": 150,
      "total_amount": 50000000.0
    }
  ]
}
```

#### TXT输出增强
```text
交互数量大于10的合约 (按交互数量排序):
----------------------------------------------------------------------
1. Contract Name
   地址: 0x1234567890abcdef1234567890abcdef12345678
   标签: Binance Hot Wallet  
   类型: exchange
   标签来源: constants
   交互次数: 150 次
   总金额: 50,000,000.00 USDT
   平均金额: 333,333.33 USDT
```

## 🚀 使用方法

### 基本使用
```bash
# 标准分析（自动启用地址标签）
python token_deposit_analyzer.py '2025-10-24 00:00:00' '2025-10-24 23:59:59' 1000000

# 指定网络和代币
python token_deposit_analyzer.py '2025-10-24 00:00:00' '2025-10-24 23:59:59' 1000000 ethereum USDT
```

### 地址标签功能状态
- ✅ **启用**: 如果`sqlite_address_querier.py`可用
- ⚠️ **禁用**: 如果无法导入地址查询器模块

## 📊 查询流程

每个地址的标签查询流程：

1. **地址常量查询** 📖
   - 查询`address_constants.py`中的预定义标签
   - 命中率统计: `constants_hits`

2. **SQLite缓存查询** 💾  
   - 查询本地SQLite数据库缓存
   - 跳过Unknown结果，继续下一步
   - 命中率统计: `sqlite_hits`

3. **外部API查询** 🌐
   - 查询Etherscan/Polygonscan/BSCScan API
   - 获取合约名称和验证状态
   - 查询统计: `api_queries`

4. **结果保存** 💿
   - 保存所有结果到SQLite（包括Unknown）
   - 更新统计: `sqlite_updates`

## 📈 日志输出示例

```
🏷️ 地址标签查询器已启用
🔍 查询地址: 0x742d35cc...6da4b7d8 (ethereum)
   ✅ 常量库命中: Binance Hot Wallet
📛 0x742d35cc...6da4b7d8: Binance Hot Wallet

🔍 查询地址: 0xa0b86a33...9b8c8d8e (ethereum)  
   🌐 查询ethereum API...
   🎯 API查询成功: Contract: TokenSwap
📛 0xa0b86a33...9b8c8d8e: Contract: TokenSwap

📊 SQLite数据库已关闭
```

## 🗃️ 数据库管理

### 查看标签数据库
```bash
python sqlite_db_manager.py view address_labels.db
```

### 搜索特定地址
```bash  
python sqlite_db_manager.py search address_labels.db 0x742d35Cc6634C0532925a3b8D2b9e9b16da4B7d8
```

### 清理Unknown记录
```bash
python sqlite_db_manager.py clean address_labels.db
```

## 🎯 性能优化

### 缓存策略
- **有效缓存**: 非Unknown结果会被缓存并复用
- **智能重试**: Unknown结果不阻止API重新查询
- **过期处理**: 缓存记录7天后过期

### API限制处理
- **查询间隔**: API查询后自动延迟0.5秒
- **错误处理**: API失败时使用默认Unknown标签
- **超时保护**: 10秒超时避免长时间等待

## 📝 配置选项

### 环境变量
```bash
# 设置API密钥以提高查询限制
export ETHERSCAN_API_KEY="your_api_key_here"
```

### 数据库位置
- 默认: `address_labels.db`
- 可在SQLiteAddressLabelQuerier初始化时指定

## 🛠️ 故障排除

### 常见问题

1. **地址标签功能未启用**
   ```
   ⚠️ sqlite_address_querier.py 未找到，地址标签功能将被禁用
   ```
   - 确保`sqlite_address_querier.py`在当前目录
   - 检查文件权限

2. **API查询失败** 
   ```
   ⚠️ ethereum API查询失败: timeout
   ```
   - 检查网络连接
   - 验证API密钥设置
   - 查看API限制状态

3. **SQLite错误**
   ```
   ❌ SQLite保存失败: database is locked
   ```
   - 关闭其他使用数据库的进程
   - 检查文件权限

## 📊 输出文件增强

### 新增字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `address_labels_enabled` | 标签功能状态 | `true/false` |
| `address_label` | 查询到的地址标签 | `"Binance Hot Wallet"` |
| `address_type` | 地址类型 | `"exchange"/"contract"/"unknown"` |
| `label_source` | 标签数据源 | `"constants"/"sqlite"/"api"/"default"` |

### 兼容性
- 原有字段保持不变
- 新字段仅在启用标签功能时添加
- 禁用时使用原有的`name`字段作为标签

## 🎉 总结

通过集成SQLite地址标签查询功能，现在的交易分析器可以：

- ✅ **自动识别知名地址** - 交易所、DeFi协议等
- ✅ **智能缓存管理** - 提高查询效率
- ✅ **详细标签信息** - 类型、来源、验证状态
- ✅ **统计数据完整** - 包含查询命中率等信息
- ✅ **向后兼容** - 不影响现有功能

享受更智能的区块链交易分析体验！🚀
#!/bin/bash
# Ganache启动脚本
# 保存为 start_ganache.sh 并执行 chmod +x start_ganache.sh

echo "🚀 启动Ganache本地以太坊节点..."

# 检查Ganache是否已安装
if ! command -v ganache &> /dev/null; then
    echo "❌ Ganache未安装，请先安装："
    echo "npm install -g ganache"
    exit 1
fi

# 启动Ganache
ganache \
  --port 8545 \
  --networkId 1337 \
  --accounts 10 \
  --defaultBalanceEther 100 \
  --gasLimit 6721975 \
  --gasPrice 20000000000 \
  --host 0.0.0.0 \
  --mnemonic "candy maple cake sugar pudding cream honey rich smooth crumble sweet treat" \
  --verbose

echo "✅ Ganache已启动在 http://localhost:8545"
echo "🔑 网络ID: 1337"
echo "💰 每个账户初始余额: 100 ETH"
echo "📝 助记词: candy maple cake sugar pudding cream honey rich smooth crumble sweet treat"
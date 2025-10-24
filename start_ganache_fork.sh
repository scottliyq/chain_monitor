#!/bin/bash
# 启动Brownie mainnet-fork环境的脚本

echo "🚀 启动Brownie mainnet-fork环境"
echo "=================================="

# 检查是否设置了API密钥
if [ -z "$WEB3_INFURA_PROJECT_ID" ] && [ -z "$WEB3_ALCHEMY_PROJECT_ID" ]; then
    echo "⚠️  未检测到API密钥，将使用免费公共RPC端点"
    echo "💡 为了更好的性能，建议设置API密钥:"
    echo "export WEB3_INFURA_PROJECT_ID='your_infura_project_id'"
    echo "或者"
    echo "export WEB3_ALCHEMY_PROJECT_ID='your_alchemy_api_key'"
    echo ""
    echo "🔄 使用免费公共RPC: https://eth.llamarpc.com"
    RPC_URL="https://eth.llamarpc.com"
else
    if [ ! -z "$WEB3_ALCHEMY_PROJECT_ID" ]; then
        if [ "$WEB3_ALCHEMY_PROJECT_ID" = "your_alchemy_api_key" ]; then
            echo "❌ WEB3_ALCHEMY_PROJECT_ID 环境变量仍为默认值 'your_alchemy_api_key'。请将其替换为您的实际Alchemy API密钥。"
            exit 1
        fi
        RPC_URL="https://eth-mainnet.g.alchemy.com/v2/$WEB3_ALCHEMY_PROJECT_ID"
        echo "✅ 使用Alchemy RPC"
    else
        if [ "$WEB3_INFURA_PROJECT_ID" = "your_infura_project_id" ]; then
            echo "❌ WEB3_INFURA_PROJECT_ID 环境变量仍为默认值 'your_infura_project_id'。请将其替换为您的实际Infura项目ID。"
            exit 1
        fi
        RPC_URL="https://mainnet.infura.io/v3/$WEB3_INFURA_PROJECT_ID"
        echo "✅ 使用Infura RPC"
    fi
fi

echo "🔗 RPC URL: $RPC_URL"

# 检查端口是否被占用
if lsof -Pi :8545 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  端口8545已被占用"
    echo "请先停止占用端口8545的进程，或选择其他端口"
    read -p "是否要停止占用端口8545的进程? (y/N): " kill_process
    if [ "$kill_process" = "y" ] || [ "$kill_process" = "Y" ]; then
        echo "停止端口8545的进程..."
        lsof -ti:8545 | xargs kill -9
        sleep 2
    else
        echo "❌ 启动取消"
        exit 1
    fi
fi

# 启动Ganache分叉
echo "🔄 启动Ganache mainnet分叉..."
echo "   端口: 8545"
echo "   网络ID: 1337"
echo "   账户数: 10"
echo "   初始余额: 1000 ETH"
echo ""

# 在后台启动Ganache
ganache \
    --fork $RPC_URL \
    --port 8545 \
    --networkId 1337 \
    --accounts 10 \
    --defaultBalanceEther 1000 \
    --gasLimit 12000000 \
    --gasPrice 20000000000 \
    --mnemonic "candy maple cake sugar pudding cream honey rich smooth crumble sweet treat" \
    --quiet &

GANACHE_PID=$!
echo "🎯 Ganache进程ID: $GANACHE_PID"

# 等待Ganache启动
echo "⏳ 等待Ganache启动..."
sleep 5

# 检查Ganache是否启动成功
if ! lsof -Pi :8545 -sTCP:LISTEN -t >/dev/null ; then
    echo "❌ Ganache启动失败"
    exit 1
fi

echo "✅ Ganache启动成功!"
echo ""
echo "📋 网络信息:"
echo "   RPC URL: http://127.0.0.1:8545"
echo "   网络ID: 1337"
echo "   分叉来源: Ethereum Mainnet"
echo ""
echo "🔧 在另一个终端中运行:"
echo "   cd /Users/scottliyq/go/hardhat_space/chain_monitor"
echo "   python brownie_mainnet_fork.py"
echo ""
echo "💡 测试账户助记词:"
echo "   candy maple cake sugar pudding cream honey rich smooth crumble sweet treat"
echo ""
echo "⚠️  按Ctrl+C停止Ganache"

# 保持运行直到用户停止
trap "echo ''; echo '🛑 停止Ganache...'; kill $GANACHE_PID 2>/dev/null; exit 0" INT

# 等待用户中断
wait $GANACHE_PID
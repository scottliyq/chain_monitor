# hardhat

这个目录只放 Hardhat 模拟链启动脚本，默认假设你已经安装好了 Hardhat。

## 快速开始

启动本地模拟链：

```bash
cd hardhat
./scripts/start-node.sh
```

默认监听地址：

- RPC: `http://127.0.0.1:8545`
- Chain ID: `31337`

如果你希望绑定到所有网卡：

```bash
HOST=0.0.0.0 ./scripts/start-node.sh
```

如果你希望 fork 一个真实网络 RPC：

```bash
cd hardhat
FORK_RPC_URL=https://ethereum-rpc.publicnode.com ./scripts/start-fork-node.sh
```
